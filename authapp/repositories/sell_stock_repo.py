from authapp.models import MarketData, UserStock
from django.db.models import Sum
from datetime import timedelta
from django.utils import timezone


def has_sufficient_stock(user, stock, quantity):
    user_stock = UserStock.objects.filter(user=user, stock=stock).first()
    if not user_stock or user_stock.quantity < quantity:
        return False

    total_stocks_in_sell_order = (
        MarketData.objects.filter(stock=stock, transaction_type="SELL").aggregate(
            total_quantity=Sum("quantity")
        )["total_quantity"]
        or 0
    )

    if total_stocks_in_sell_order + quantity > user_stock.quantity:
        return False

    return True


def is_t_plus_3_restricted(user, stock):
    user_stock = UserStock.objects.filter(user=user, stock=stock).first()
    if user_stock and timezone.now() < user_stock.purchase_date + timedelta(days=3):
        return True
    return False


def place_sell_order(user, stock, quantity, price):
    MarketData.objects.create(
        user=user,
        stock=stock,
        transaction_type="SELL",
        quantity=quantity,
        price=price,
        transaction_date=timezone.now(),
    )
