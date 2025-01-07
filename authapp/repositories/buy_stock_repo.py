from django.utils import timezone

from authapp.models import MarketData, Transaction, UserStock


# Helper to validate the buyer's balance
def validate_buyer_balance(user, total_cost):
    if user.account_balance < total_cost:
        return {"error": "Insufficient balance"}
    return None


# Helper to calculate total cost and validate market availability
def validate_market_data(stock, price, quantity):
    market_data_queryset = MarketData.objects.filter(
        stock=stock, transaction_type="SELL", price__lte=price
    ).order_by("price")

    total_quantity_available = sum(m.quantity for m in market_data_queryset)
    if total_quantity_available < quantity:
        return {"error": "Not enough matching sell orders on the market"}, None
    return None, market_data_queryset


def process_transactions(user, stock, quantity, price, market_data_queryset):
    total_cost = 0
    initial_quantity = quantity
    buyer_transactions = []
    seller_transactions = []

    for sell_order in market_data_queryset:
        quantity_to_buy = min(sell_order.quantity, quantity)

        # Create BUY transaction for buyer
        buyer_transaction = Transaction.objects.create(
            user=user,
            stock=stock,
            transaction_type="BUY",
            quantity=quantity_to_buy,
            price=sell_order.price,
            status="COMPLETED",
            transaction_date=timezone.now(),
        )
        buyer_transactions.append(buyer_transaction)

        # Create SELL transaction for seller
        seller_transaction = Transaction.objects.create(
            user=sell_order.user,
            stock=stock,
            transaction_type="SELL",
            quantity=quantity_to_buy,
            price=sell_order.price,
            status="COMPLETED",
            transaction_date=timezone.now(),
        )
        seller_transactions.append(seller_transaction)

        # Update seller's UserStock
        seller_stock = UserStock.objects.get(user=sell_order.user, stock=stock)
        if seller_stock.sold_quantity < quantity_to_buy:
            raise ValueError("Sold quantity mismatch during transaction")

        seller_stock.sold_quantity -= quantity_to_buy
        seller_stock.save()

        # Update sell order
        sell_order.quantity -= quantity_to_buy
        if sell_order.quantity == 0:
            sell_order.delete()
        else:
            sell_order.save()

        total_cost += quantity_to_buy * sell_order.price
        quantity -= quantity_to_buy
        if quantity == 0:
            break

    return total_cost, initial_quantity, buyer_transactions, seller_transactions


# Helper to update user stocks and balances after transactions
def update_user_stock_and_balance(
    user, stock, initial_quantity, total_cost, buyer_transactions, seller_transactions
):
    # Update buyer stock
    user_stock, created = UserStock.objects.get_or_create(
        user=user, stock=stock, defaults={"quantity": 0, "sold_quantity": 0}
    )
    user_stock.quantity += initial_quantity
    user_stock.save()

    # Decrease buyer's balance
    user.account_balance -= total_cost
    user.save()

    # Update seller stocks and balances
    for transaction in seller_transactions:
        seller = transaction.user
        seller.account_balance += transaction.quantity * transaction.price
        seller.save()
