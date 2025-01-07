from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from stocks.models import Stock


# Create your models here.


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CustomUserManager(BaseUserManager):
    def create_user(self, username, password, **extra_fields):
        if not username:
            raise ValueError("The Username field must be set")
        if not password:
            raise ValueError("The Password field must be set")

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault("role", "Admin")
        return self.create_user(username, password, **extra_fields)


class Role(BaseModel):
    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("User", "User"),
        ("Guest", "Guest"),
        ("VIP", "VIP"),
        ("Collaborator", "Collaborator"),
    ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, choices=ROLE_CHOICES)
    # name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class User(AbstractBaseUser, BaseModel):
    username = models.CharField(max_length=255, unique=True, null=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, null=False, default=1)
    stocks_followed = models.ManyToManyField(Stock, through="UserStockFollowed")
    account_balance = models.DecimalField(
        default=Decimal("0.00"), max_digits=10, decimal_places=2
    )

    USERNAME_FIELD = "username"  # default: email
    REQUIRED_FIELDS = ["password", "role"]

    objects = CustomUserManager()

    def __str__(self):
        return self.username


class UserStockFollowed(BaseModel):
    user = models.ForeignKey(
        User, related_name="user_stocks_followed", on_delete=models.CASCADE
    )
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} - {self.stock.id}"


class UserStock(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    sold_quantity = models.PositiveIntegerField(default=0)
    purchase_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} owns {self.quantity} of {self.stock.id}"


class Permission(BaseModel):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class RolePermission(BaseModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"


class Transaction(BaseModel):
    TRANSACTION_TYPE = [
        ("BUY", "Buy"),
        ("SELL", "Sell"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=4, choices=TRANSACTION_TYPE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=20, decimal_places=2)
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Pending")

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} {self.stock.id} for {self.user.username} "


class MarketData(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=20, decimal_places=2)
    transaction_type = models.CharField(max_length=50)
    transaction_date = models.DateTimeField()

    def __str__(self):
        return f"{self.stock.id} - {self.quantity} - {self.price}"

    @property
    def total_price(self):
        return self.quantity * self.price


class Order(BaseModel):
    ORDER_TYPES = [
        ("BUY", "Buy"),
        ("SELL", "Sell"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("EXECUTED", "Executed"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    ORDER_MODES = [
        ("MARKET", "Market"),
        ("LIMIT", "Limit"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=4, choices=ORDER_TYPES)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=20, decimal_places=2)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    order_mode = models.CharField(max_length=6, choices=ORDER_MODES)
    can_execute_date = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kargs):
        if self.order_date is None:
            self.order_date = timezone.now()
        if self.order_type == "BUY":
            self.can_excute_date = self.order_date + timedelta(days=3)
            self.status = "PENDING"
        super().save(*args, **kargs)

    def __str__(self):
        return f"Order {self.order_type} {self.quantity} {self.stock.id} for {self.user.username}"
