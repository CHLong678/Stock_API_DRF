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

    @db_transaction.atomic
    def create(self, request):
        user = request.user
        serializer = TransactionSerializer(data=request.data)

        if serializer.is_valid():
            transaction_type = serializer.validated_data["transaction_type"]
            stock = serializer.validated_data["stock"]
            quantity = serializer.validated_data["quantity"]
            price = serializer.validated_data["price"]

            transaction = None

            if transaction_type == "BUY":
                # Kiểm tra số dư tài khoản người mua
                if user.account_balance < price * quantity:
                    return Response(
                        {"error": "Insufficient balance"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Lấy danh sách lệnh bán hợp lệ từ MarketData
                market_data_queryset = MarketData.objects.filter(
                    stock=stock,
                    transaction_type="SELL",
                    price__lte=price,
                ).order_by("price")

                total_quantity_available = sum(m.quantity for m in market_data_queryset)
                if total_quantity_available < quantity:
                    return Response(
                        {"error": "Not enough matching sell orders on the market"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                total_cost = 0
                initial_quantity = quantity  # Lưu lại số lượng ban đầu của người mua
                # Khớp lệnh từng phần với các lệnh bán
                for sell_order in market_data_queryset:
                    quantity_to_buy = min(sell_order.quantity, quantity)

                    # Tạo giao dịch cho người mua
                    transaction = Transaction.objects.create(
                        user=user,
                        stock=stock,
                        transaction_type="BUY",
                        quantity=quantity_to_buy,
                        price=sell_order.price,
                        status="COMPLETED",
                        transaction_date=timezone.now(),
                    )

                    # Cập nhật lệnh bán trên MarketData
                    sell_order.quantity -= quantity_to_buy
                    if sell_order.quantity == 0:
                        sell_order.delete()  # Nếu lệnh bán hết, xóa lệnh
                    else:
                        sell_order.save()

                    total_cost += quantity_to_buy * sell_order.price

                    quantity -= quantity_to_buy
                    if quantity == 0:
                        break

                # Trừ số tiền thực tế từ tài khoản người mua
                user.account_balance -= total_cost
                user.save()

                # Cập nhật cổ phiếu cho người mua
                user_stock, created = UserStock.objects.get_or_create(
                    user=user,
                    stock=stock,
                    defaults={
                        "quantity": initial_quantity
                    },  # Cập nhật theo số lượng ban đầu
                )
                if not created:
                    user_stock.quantity += initial_quantity
                    user_stock.save()

                # Cập nhật tài khoản người bán
                for sell_order in market_data_queryset:
                    if sell_order.transaction_type == "SELL":
                        seller = sell_order.user
                        # Cộng tiền vào tài khoản người bán
                        seller.account_balance += total_cost
                        seller.save()

                        # Giảm số lượng cổ phiếu của người bán
                        user_stock = UserStock.objects.filter(
                            user=seller, stock=stock
                        ).first()
                        if user_stock:
                            user_stock.quantity -= (
                                quantity_to_buy  # Giảm theo số lượng đã bán
                            )
                            user_stock.save()

            elif transaction_type == "SELL":
                # Kiểm tra cổ phiếu người dùng sở hữu
                user_stock = UserStock.objects.filter(user=user, stock=stock).first()
                if not user_stock or user_stock.quantity < quantity:
                    return Response(
                        {"error": "Not enough stock to sell"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Kiểm tra thời gian mua (T+3)
                if timezone.now() < user_stock.purchase_date + timedelta(days=3):
                    return Response(
                        {"error": "Cannot sell stock before T+3"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Tạo lệnh bán vào MarketData, không cộng tiền ngay
                MarketData.objects.create(
                    user=user,
                    stock=stock,
                    transaction_type="SELL",
                    quantity=quantity,
                    price=price,
                    transaction_date=timezone.now(),
                )

                return Response(
                    {"message": "Sell order placed successfully"},
                    status=status.HTTP_201_CREATED,
                )

            if transaction:
                transaction_serializer = TransactionSerializer(transaction)
                return Response(
                    transaction_serializer.data, status=status.HTTP_201_CREATED
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        user = request.user
        transactions = Transaction.objects.filter(user=user)
        transaction_serializer = TransactionSerializer(transactions, many=True)
        return Response(transaction_serializer.data, status=status.HTTP_200_OK)
