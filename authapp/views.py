from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from django.db.models import Sum
from django.db import transaction as db_transaction


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
    has_sufficient_stock,
    is_t_plus_3_restricted,
    place_sell_order,
)


# Create your views here.


class SignUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = SignUpSerializer(data=request.data)
        if serializer.is_valid():
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


class RoleView(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def create(self, request):
        serializer = RoleSerializer(data=request.data)
        if serializer.is_valid():
            if Role.objects.filter(name=serializer.validated_data["name"]).exists():
                return Response(
                    {"error": "Role already exists"}, status=status.HTTP_400_BAD_REQUEST
                )
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            role = Role.objects.get(pk=pk)
        except Role.DoesNotExist:
            return Response(
                {"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = RoleSerializer(role, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Role updated successfully", "data": serializer.data},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            role = Role.objects.get(pk=pk)
            role.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Role.DoesNotExist:
            return Response(
                {"error": "Role not found"}, status=status.HTTP_404_NOT_FOUND
            )


class AccountView(viewsets.ViewSet):
    permission_classes = [CanAddMoneyPermission]

    @action(detail=False, methods=["put"], url_path="add-money")
    def add_money(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            raise NotFound("User not found")

        serializer = AddMoneySerializer(data=request.data)
        if serializer.is_valid():
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


"""
Admin can control permissions
"""


class PermissionView(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        permissions = Permission.objects.all()
        serializer = PermissionSerializer(permissions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request):
        serializer = PermissionSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            permission = Permission.objects.get(pk=pk)
        except Permission.DoesNotExist:
            raise NotFound("Permission not found")

        serializer = PermissionSerializer(permission, data=request.data, partial=True)
        if serializer.is_valid():
            permission = serializer.save()
            return Response(
                {"message": "Permission updated successfully", "data": serializer.data},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            permission = Permission.objects.get(pk=pk)
        except Permission.DoesNotExist:
            raise NotFound("Permission not found")

        permission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


"""
Admin can control specific role's permissons 
- Such as: Admin can add a permission named "can_add_money" to the "User" role
"""


class RolePermissionView(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        role_permissions = RolePermission.objects.all()
        serializer = RolePermissionSerializer(role_permissions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def create(self, request):
        serializer = RolePermissionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Role permission created successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        try:
            role_permission = RolePermission.objects.get(pk=pk)
        except RolePermission.DoesNotExist:
            raise NotFound("Role permission not found")

        serializer = RolePermissionSerializer(
            role_permission,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Role permission updated successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        try:
            role_permission = RolePermission.objects.get(pk=pk)
        except RolePermission.DoesNotExist:
            raise NotFound("Role permission not found")
        role_permission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserDetailViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def profile(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Get information user's transaction
    """

    permission_classes = [IsAuthenticated]

    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class MarketDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MarketData.objects.filter(transaction_type="SELL")
    serializer_class = MarketDataSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class UserStockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Get information about stocks of one user
    """

    permission_classes = [IsAuthenticated]

    queryset = UserStock.objects.all()
    serializer_class = UserStockSerializer

    def get_queryset(self):
        return UserStock.objects.filter(user=self.request.user)


class TransactionBuySellViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        transactions = Transaction.objects.filter(user=user)
        transaction_serializer = TransactionSerializer(transactions, many=True)
        return Response(transaction_serializer.data, status=status.HTTP_200_OK)

    @db_transaction.atomic
    @action(detail=False, methods=["post"], url_path="sell")
    def sell(self, request):
        user = request.user
        serializer = TransactionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        stock = serializer.validated_data["stock"]
        quantity = serializer.validated_data["quantity"]
        price = serializer.validated_data["price"]

        # Validate stock availability
        if not has_sufficient_stock(user, stock, quantity):
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

        # Place the sell order
        place_sell_order(user, stock, quantity, price)

        return Response(
            {"message": "Sell order placed successfully"},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def cancel_sell(self, request, order_id):
        user = request.user
        print(f"User: {user}, Order ID: {order_id}")

        # Find the sell_order
        try:
            sell_order = MarketData.objects.get(
                id=order_id, user=user, transaction_type="SELL"
            )
            print(sell_order)
        except MarketData.DoesNotExist:
            return Response(
                {
                    "error": "Sell order not found or you are not the owner of this order"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if the sell_order had been bought
        if MarketData.objects.filter(
            stock=sell_order.stock, transaction_type="BUY", price=sell_order.price
        ).exists():
            return Response(
                {
                    "error": "Cannot cancel sell order because it has already been bought"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cancel sell_order if no one buy
        sell_order.delete()

        return Response(
            {"message": "Sell order cancelled successfully"},
            status=status.HTTP_200_OK,
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
        total_cost, initial_quantity, buyer_transactions, seller_transactions = (
            process_transactions(user, stock, quantity, price, market_data_queryset)
        )

        # Update stocks and balances
        update_user_stock_and_balance(
            user,
            stock,
            initial_quantity,
            total_cost,
            buyer_transactions,
            seller_transactions,
        )

        # Serialize transactions
        buyer_transaction_serializer = TransactionSerializer(
            buyer_transactions, many=True
        )
        seller_transaction_serializer = TransactionSerializer(
            seller_transactions, many=True
        )

        return Response(
            {"buyer_transactions": buyer_transaction_serializer.data},
            status=status.HTTP_201_CREATED,
        )
