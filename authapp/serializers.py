from django.utils import timezone
from rest_framework import serializers

from .models import (
    User,
    Role,
    UserStockFollowed,
    Permission,
    RolePermission,
    Order,
    MarketData,
    Transaction,
    UserStock,
)


# Create your serializers here.


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "role",
            "stocks_followed",
            "account_balance",
        ]
        read_only_fields = ["id", "role"]


class SignUpSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(
        queryset=Role.objects.all(), slug_field="name", required=False
    )

    class Meta:
        model = User
        fields = ["username", "password", "role"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def create(self, validated_data):
        role = validated_data.get(
            "role",
            Role.objects.get(name="User"),
        )

        user = User.objects.create_user(
            validated_data["username"],
            validated_data["password"],
            role=role,
        )
        return user


class UserStockFollowedSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    stock = serializers.StringRelatedField()
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UserStockFollowed
        fields = ["user", "stock", "created_at", "updated_at"]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "name", "description"]


class RolePermissionSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(queryset=Role.objects.all(), slug_field="name")
    permission = serializers.SlugRelatedField(
        queryset=Permission.objects.all(), slug_field="name"
    )

    class Meta:
        model = RolePermission
        fields = ["id", "role", "permission", "created_at", "updated_at"]


class AddMoneySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be a positive number.")
        return value


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "stock",
            "order_type",
            "quantity",
            "price",
            "order_mode",
            "status",
            "order_date",
        ]

    def create(self, validated_data):
        if "order_date" not in validated_data or validated_data["order_date"] is None:
            validated_data["order_date"] = timezone.now()

        order = Order.objects.create(**validated_data)
        return order


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "stock",
            "transaction_type",
            "quantity",
            "price",
            "transaction_date",
            "status",
        ]


class MarketDataSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = MarketData
        fields = [
            "id",
            "username",
            "stock",
            "quantity",
            "price",
            "transaction_type",
            "transaction_date",
        ]


class UserStockSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserStock
        fields = ["id", "user_id", "username", "stock", "quantity"]


class BuyStockSerializer(serializers.Serializer):
    stock_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
