from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets, mixins
from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny,
    IsAuthenticatedOrReadOnly,
)
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework.decorators import action
from django.db import transaction as db_transaction
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend


from .serializers import (
    MarketDataSerializer,
    SignUpSerializer,
    RoleSerializer,
    AddMoneySerializer,
    PermissionSerializer,
    RolePermissionSerializer,
    TransactionSerializer,
    UserSerializer,
    UserStockSerializer,
)
from stocks.permissions import IsAdminUser
from .permissions import CanAddMoneyPermission
from .models import (
    MarketData,
    Role,
    Transaction,
    User,
    Permission,
    RolePermission,
    UserStock,
)
from .repositories.buy_stock_repo import (
    validate_buyer_balance,
    validate_market_data,
    process_transactions,
    update_user_stock_and_balance,
)

from .repositories.sell_stock_repo import (
    fetch_user_stock,
    has_sufficient_stock,
    is_t_plus_3_restricted,
    process_sell_order,
)


# Create your views here.


# Helper for validating response
def is_valid_response(serializer, error_status=status.HTTP_400_BAD_REQUEST):
    if serializer.is_valid():
        return None
    return Response(serializer.errors, status=error_status)


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class BaseReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    # ordering_fields = ["created_at", "updated_at"]


class BaseUserRelatedViewSet(BaseReadOnlyViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if hasattr(self, "queryset") and self.queryset:
            return self.queryset.filter(user=self.request.user)
        else:
            return UserStock.objects.none()


class SignUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = SignUpSerializer(data=request.data)
        validation_response = is_valid_response(serializer)
        if not serializer.is_valid():
            return validation_response

        user = serializer.save()
        return Response(
            {
                "message": "User created successfully",
                "data": {
                    "id": user.id,
                    "username": user.username,
                    "role": user.role.name,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LogOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh", None)
            access_token = request.data.get("access", None)

            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            if access_token:
                access_token = AccessToken(access_token)
                access_token.blacklist()

            return Response(
                {"message": "Successfully logged out"}, status=status.HTTP_200_OK
            )

        except Exception:
            return Response(
                {"error": "Unable to logout"}, status=status.HTTP_400_BAD_REQUEST
            )


class RoleView(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class AccountView(viewsets.GenericViewSet):
    permission_classes = [CanAddMoneyPermission]

    @action(detail=False, methods=["put"], url_path="add-money")
    def add_money(self, request, pk=None):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = AddMoneySerializer(data=request.data)
        validation_response = is_valid_response(serializer)
        if validation_response:
            return validation_response

        amount = serializer.validated_data["amount"]
        user.account_balance += amount
        user.save()
        return Response(
            {
                "message": "Balance updated successfully",
                "new_balance": user.account_balance,
            },
            status=status.HTTP_200_OK,
        )


"""
Admin can control permissions
"""


class PermissionView(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer


"""
Admin can control specific role's permissons 
- Such as: Admin can add a permission named "can_add_money" to the "User" role
"""


class RolePermissionView(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAdminUser]
    queryset = RolePermission.objects.all()
    serializer_class = RolePermissionSerializer


class UserDetailViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @action(detail=False, methods=["get"], url_path="profile")
    def profile(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


# class TransactionViewSet(BaseUserRelatedViewSet):
#     """
#     Get information user's transaction
#     """

#     queryset = Transaction.objects.all()
#     serializer_class = TransactionSerializer
#     filterset_fields = ["transaction_type", "stock"]
#     ordering_fields = ["created_at", "amount"]
#     search_fields = ["stock__id"]


class MarketDataViewSet(BaseReadOnlyViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = MarketDataSerializer
    filterset_fields = ["stock", "price"]
    ordering_fields = ["price", "updated_at"]
    search_fields = ["stock__id"]

    def get_queryset(self):
        return MarketData.objects.filter(transaction_type="SELL")


class UserStockViewSet(BaseUserRelatedViewSet):
    """
    Get information about stocks of one user
    """

    queryset = UserStock.objects.select_related("stock")
    serializer_class = UserStockSerializer
    filterset_fields = ["stock"]
    ordering_fields = ["quantity", "updated_at"]
    search_fields = ["stock__id"]


class TransactionBuySellViewSet(
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "list":
            return [AllowAny()]

    def list(self, request):
        user = request.user
        transactions = Transaction.objects.filter(user=user)
        transaction_serializer = TransactionSerializer(transactions, many=True)
        return Response(transaction_serializer.data, status=status.HTTP_200_OK)

    @db_transaction.atomic
    @action(detail=False, methods=["post"], url_path="sell")
    def sell(self, request):
        """
        Handle the process of selling stocks, including validation and order placement.
        """
        user = request.user
        serializer = TransactionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        stock = serializer.validated_data["stock"]
        quantity = serializer.validated_data["quantity"]
        price = serializer.validated_data["price"]

        # Get UserStock object and lock it for update
        user_stock = fetch_user_stock(user=user, stock=stock)

        if not user_stock:
            return Response(
                {"message": "User does not own this stock"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate stock availability based on `quantity`
        if user_stock.quantity < quantity:
            return Response(
                {"error": "Not enough stock to sell"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate T+3 rule
        if is_t_plus_3_restricted(user, stock):
            return Response(
                {"error": "Cannot sell stock before T+3"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        process_sell_order(user_stock, stock, quantity, price)

        return Response(
            {"message": "Sell order placed successfully"},
            status=status.HTTP_201_CREATED,
        )

    @db_transaction.atomic
    @action(detail=False, methods=["post"], url_path="buy")
    def buy(self, request):
        user = request.user
        serializer = TransactionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        stock = serializer.validated_data["stock"]
        quantity = serializer.validated_data["quantity"]
        price = serializer.validated_data["price"]

        # Validate buyer's balance
        total_cost = price * quantity
        error = validate_buyer_balance(user, total_cost)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        # Validate market data
        error, market_data_queryset = validate_market_data(stock, price, quantity)
        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        # Process transactions for both buyer and seller
        (
            total_cost,
            initial_quantity,
            buyer_transactions,
            seller_transactions,
        ) = process_transactions(user, stock, quantity, price, market_data_queryset)

        # Update stocks and balances
        update_user_stock_and_balance(
            user,
            stock,
            initial_quantity,
            total_cost,
            buyer_transactions,
            seller_transactions,
        )

        buyer_transaction_serializer = TransactionSerializer(
            buyer_transactions, many=True
        )
        seller_transaction_serializer = TransactionSerializer(  # noqa: F841
            seller_transactions, many=True
        )

        return Response(
            {
                "buyer_transactions": buyer_transaction_serializer.data,
                # "seller_transactions": seller_transaction_serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
