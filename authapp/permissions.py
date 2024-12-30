from rest_framework.permissions import BasePermission
from .models import RolePermission


class CanAddMoneyPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        role = request.user.role

        if RolePermission.objects.filter(
            role=role, permission__name="can_add_money"
        ).exists():
            return True

        return False
