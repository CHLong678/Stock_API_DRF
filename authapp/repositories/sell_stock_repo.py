from authapp.models import MarketData, UserStock
from datetime import timedelta
from django.utils import timezone
from django.db.models import F


def fetch_user_stock(user, stock):
    """
    Fetch the UserStock object and lock it for update.
    """
    try:
        return UserStock.objects.select_for_update().get(user=user, stock=stock)
    except UserStock.DoesNotExist:
        return None


def has_sufficient_stock(user_stock, quantity):
    """
    Check if the user has enough stock to sell.
    """
    return user_stock.quantity >= quantity


def is_t_plus_3_restricted(user, stock):
    """
    Check if the stock cannot be sold due to the T+3 restriction.
    """
    purchase_date = (
        MarketData.objects.filter(user=user, stock=stock, transaction_type="BUY")
        .order_by("transaction_date")
        .values_list("transaction_date", flat=True)
        .first()
    )

    if purchase_date and timezone.now() < purchase_date + timedelta(days=3):
        return True
    return False


def process_sell_order(user_stock, stock, quantity, price):
    """
    Update UserStock and create a sell order in MarketData.
    """
    # Update UserStock
    user_stock.quantity = F("quantity") - quantity
    user_stock.sold_quantity = F("sold_quantity") + quantity
    user_stock.save()

    # Create the sell order
    MarketData.objects.create(
        user=user_stock.user,
        stock=stock,
        transaction_type="SELL",
        quantity=quantity,
        price=price,
        transaction_date=timezone.now(),
    )
