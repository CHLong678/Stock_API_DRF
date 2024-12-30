from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from django.db import transaction as db_transaction


from .serializers import (
    MarketDataSerializer,
    SignUpSerializer,
    RoleSerializer,
    AddMoneySerializer,
    PermissionSerializer,
    RolePermissionSerializer,
    OrderSerializer,
    TransactionSerializer,
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
    Order,
    UserStock,
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


class OrderViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @db_transaction.atomic
    def create(self, request):
        user = request.user
        serializer = OrderSerializer(data=request.data)

        if serializer.is_valid():
            order = serializer.save(user=user)
            stock = order.stock
            quantity = order.quantity
            price = order.price

            if order.order_type == "BUY":
                if user.account_balance < price * quantity:
                    return Response(
                        {"error": "Insufficient balance"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                user.account_balance -= price * quantity
                user.save()

                transaction = Transaction.objects.create(
                    user=user,
                    stock=stock,
                    transaction_type="BUY",
                    quantity=quantity,
                    price=price,
                    status="PENDING",
                    transaction_date=timezone.now(),
                )

                order.can_execute_date = timezone.now() + timedelta(days=3)
                order.save()

            elif order.order_type == "SELL":
                user_stock = UserStock.objects.filter(user=user, stock=stock).first()
                if not user_stock or user_stock.quantity < quantity:
                    return Response(
                        {"error": "Not enough stock to sell"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                transaction = Transaction.objects.create(
                    user=user,
                    stock=stock,
                    transaction_type="SELL",
                    quantity=quantity,
                    price=price,
                    status="PENDING",
                    transaction_date=timezone.now(),
                )

                order.can_execute_date = timezone.now() + timedelta(days=3)
                order.save()

            transaction_serializer = TransactionSerializer(transaction)
            order_serializer = OrderSerializer(order)
            return Response(order_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    """
    Get information about stock on market
    """

    permission_classes = [IsAuthenticated]

    queryset = MarketData.objects.all()
    serializer_class = MarketDataSerializer

    def get_queryset(self):
        return MarketData.objects.filter(user=self.request.user)


class UserStockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Get information about stocks of one user
    """

    permission_classes = [IsAuthenticated]

    queryset = UserStock.objects.all()
    serializer_class = UserStockSerializer

    def get_queryset(self):
        return UserStock.objects.filter(user=self.request.user)


class ExecuteOrderViewSet(viewsets.ViewSet):
    @db_transaction.atomic
    def update(self, request, pk=None):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if timezone.now() < order.can_execute_date:
            return Response(
                {"error": "Order cannot be executed yet (T+3 rule)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status == "PENDING":
            if order.order_type == "BUY":
                transaction = Transaction.objects.create(
                    user=order.user,
                    stock=order.stock,
                    transaction_type="BUY",
                    quantity=order.quantity,
                    price=order.price,
                    status="COMPLETED",
                    transaction_date=timezone.now(),
                )

                user_stock, created = UserStock.objects.get_or_create(
                    user=order.user,
                    stock=order.stock,
                    defaults={
                        "quantity": order.quantity,
                    },
                )

                if not created:
                    user_stock.quantity += order.quantity
                    user_stock.save()

            elif order.order_type == "SELL":
                user_stock = UserStock.objects.filter(
                    user=order.user, stock=order.stock
                ).first()

                if user_stock.quantity < order.quantity:
                    return Response(
                        {"error": "Not enough stock to sell"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                user_stock.quantity -= order.quantity
                user_stock.save()

                transaction = Transaction.objects.create(
                    user=order.user,
                    stock=order.stock,
                    transaction_type="SELL",
                    quantity=order.quantity,
                    price=order.price,
                    status="COMPLETED",
                    transaction_date=timezone.now(),
                )

                market_data = MarketData.objects.create(
                    user=order.user,
                    stock=order.stock,
                    transaction_type="SELL",
                    quantity=order.quantity,
                    price=order.price,
                    transaction_date=timezone.now(),
                )
                market_data_serializer = MarketDataSerializer(market_data)

            order.status = "COMPLETED"
            order.save()

            transaction_serializer = TransactionSerializer(transaction)

            return Response(transaction_serializer.data, status=status.HTTP_200_OK)

        return Response(
            {"error": "Order already processed"}, status=status.HTTP_400_BAD_REQUEST
        )
