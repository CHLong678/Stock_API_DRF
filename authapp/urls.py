from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    SignUpView,
    RoleView,
    AccountView,
    PermissionView,
    RolePermissionView,
    UserDetailViewSet,
    MarketDataViewSet,
    UserStockViewSet,
    TransactionBuySellViewSet,
)
from django.urls import include, path

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"permissions", PermissionView, basename="permissions")
router.register(r"role-permissions", RolePermissionView, basename="role_permissions")
router.register(r"roles", RoleView, basename="roles")
router.register(r"transactions", TransactionBuySellViewSet, basename="transaction")
router.register(r"marketdata", MarketDataViewSet, basename="market-data")
router.register(r"userstocks", UserStockViewSet, basename="user-stock")
router.register(r"users", UserDetailViewSet, basename="user-detail")

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "accounts/<int:pk>/add-money/",
        AccountView.as_view({"put": "add_money"}),
        name="add_money",
    ),
    path("", include(router.urls)),
]
