from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import requests
from rest_framework.pagination import PageNumberPagination

from .models import Stock
from .serializers import StockSerializer, AddStocksFollowSerializer
from .permissions import IsAdminUser, IsUserOrReadOnly
from authapp.models import UserStockFollowed


class StockViewSet(viewsets.ModelViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [IsAdminUser | IsUserOrReadOnly]
    pagination_class = PageNumberPagination

    def paginate_queryset(self, queryset, request):
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(paginated_queryset)

    @action(detail=False, methods=["get"], url_path="market-price")
    def get_market_price(self, request):
        stocks = Stock.objects.values("id", "name", "marketPrice")
        return self.paginate_queryset(stocks, request)

    @action(detail=False, methods=["get"], url_path="section-index")
    def get_section_index(self, request):
        stocks = Stock.objects.values("id", "name", "sectionIndex")
        return self.paginate_queryset(stocks, request)


class UserStockFollowViewSet(
    viewsets.GenericViewSet,
    viewsets.mixins.ListModelMixin,
    viewsets.mixins.CreateModelMixin,
):
    permission_classes = [IsAuthenticated]
    serializer_class = AddStocksFollowSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return AddStocksFollowSerializer
        return StockSerializer

    def get_queryset(self):
        user = self.request.user
        followed_stocks = UserStockFollowed.objects.filter(user=user).select_related(
            "stock"
        )

        return [fs.stock for fs in followed_stocks]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stock_symbols = serializer.validated_data["stock_symbols"]
        user = request.user

        stocks = Stock.objects.filter(id__in=stock_symbols)

        followed_stocks = UserStockFollowed.objects.filter(
            user=user, stock__in=stocks
        ).values_list("stock_id", flat=True)

        already_followed = list(set(followed_stocks))
        not_followed_symbols = set(stock_symbols) - set(already_followed)

        not_followed_stocks = stocks.filter(id__in=not_followed_symbols)

        UserStockFollowed.objects.bulk_create(
            [UserStockFollowed(user=user, stock=stock) for stock in not_followed_stocks]
        )

        return Response(
            {
                "added_stocks": list(not_followed_symbols),
                "already_followed": already_followed,
            },
            status=status.HTTP_201_CREATED,
        )


# Get current stock's price
class StockPriceView(viewsets.ViewSet):
    """
    ViewSet for fetching stock's current price from external API.
    """

    permission_classes = [IsAuthenticated]

    def get_stock_price(self, request, symbol=None):
        url = f"https://fwtapi4.fialda.com/api/services/app/Stock/GetIntraday?symbol={symbol}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return Response(data, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException as e:
            return Response(
                {"error": "Failed to fetch stock data", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
