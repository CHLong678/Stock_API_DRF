from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import requests
from django.db import transaction
from rest_framework.pagination import PageNumberPagination


from authapp.serializers import BuyStockSerializer


from .models import Stock
from .serializers import StockSerializer, AddStocksFollowSerializer
from .permissions import IsAdminUser, IsUserOrReadOnly
from authapp.models import UserStock, UserStockFollowed


class StockViewSet(viewsets.ViewSet):
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [IsAdminUser | IsUserOrReadOnly]

    def create(self, request):
        self.check_permissions(request)
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        raise ValueError(
            serializer.errors,
            "Invalid data",
        )

    def update(self, request, pk=None):
        self.check_permissions(request)
        try:
            stock = Stock.objects.get(pk=pk)
        except Stock.DoesNotExist:
            raise ValueError("Stock not found")

        serializer = self.serializer_class(stock, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        raise ValueError(
            serializer.errors,
            "Invalid data",
        )

    def destroy(self, request, pk=None):
        self.check_permissions(request)
        try:
            stock = Stock.objects.get(pk=pk)
            stock.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Stock.DoesNotExist:
            raise ValueError("Stock not found")

    def list(self, request):
        stocks = Stock.objects.all()
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(stocks, request)
        if page is not None:
            serializer = self.serializer_class(page, many=True)
            return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=["get"], url_path="market-price")
    def get_market_price(self, request):
        stocks = Stock.objects.values("id", "name", "marketPrice")
        return Response(stocks, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="section-index")
    def get_section_index(self, request):
        stocks = Stock.objects.values("id", "name", "sectionIndex")
        return Response(stocks, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="stock-detail")
    def get_stock_detail(self, request, pk=None):
        try:
            stock = Stock.objects.get(pk=pk)
            serializer = self.serializer_class(stock)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Stock.DoesNotExist:
            return Response(
                {"error": "Stock not found"}, status=status.HTTP_404_NOT_FOUND
            )


class UserStockFollowViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        serializer = AddStocksFollowSerializer(data=request.data)
        if serializer.is_valid():
            stock_symbols = serializer.validated_data["stock_symbols"]
            user = request.user

            added_stocks = []
            already_followed = []
            for symbol in stock_symbols:
                stock = Stock.objects.get(id=symbol)
                if UserStockFollowed.objects.filter(user=user, stock=stock).exists():
                    already_followed.append(symbol)
                else:
                    UserStockFollowed.objects.create(user=user, stock=stock)
                    added_stocks.append(symbol)

            return Response(
                {
                    "added_stocks": added_stocks,
                    "already_followed": already_followed,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def list(self, request):
        user = request.user
        followed_stocks = UserStockFollowed.objects.filter(user=user).select_related(
            "stock"
        )
        stocks = [fs.stock for fs in followed_stocks]
        serializer = StockSerializer(stocks, many=True)
        return Response(serializer.data)


# Get current stock's price
class StockPriceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, symbol):
        url = f"https://fwtapi4.fialda.com/api/services/app/Stock/GetIntraday?symbol={symbol}"

        try:
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Failed to fetch stock data"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except requests.exceptions.RequestException as e:
            return Response(
                {"Error fetching data": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StockTransactionView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def buy_stock(self, request):
        serializer = BuyStockSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        stock_id = serializer.validated_data["stock_id"]
        quantity = serializer.validated_data["quantity"]
        price = serializer.validated_data["price"]

        stock = get_object_or_404(Stock, id=stock_id)
        total_price = Decimal(quantity) * Decimal(price)

        if user.account_balance < total_price:
            return Response(
                {"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if user.account_balance < total_price:
                return Response(
                    {"error": "Insufficient balance"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.account_balance -= total_price
            user.save()

            # Update UserStock
            user_stock, created = UserStock.objects.get_or_create(
                user=user, stock=stock, defaults={"quantity": 0}
            )
            user_stock.total_quantity += quantity

            user_stock.save()
