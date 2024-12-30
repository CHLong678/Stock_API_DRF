from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import StockViewSet, UserStockFollowViewSet, StockPriceView


router = DefaultRouter()
router.register(r"stocks", StockViewSet, basename="stocks")

urlpatterns = [
    path(
        "stocks/follow/",
        UserStockFollowViewSet.as_view(
            {"get": "list"}
        ),  # get list stock follow by user
        name="follow_list",
    ),
    path(
        "stocks/follow/add/",
        UserStockFollowViewSet.as_view({"post": "create"}),  # add stock follow by user
        name="follow_add",
    ),
    path(
        "stocks/<symbol>/price/",
        StockPriceView.as_view(),  # Get current info stocks
        name="get_stock_price",
    ),
    path("", include(router.urls)),
]
