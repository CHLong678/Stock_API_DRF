from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        if request.user.is_authenticated and request.user.role.name == "Admin":
            return True
        return False


class IsUserOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method == "GET":
            return True
        if request.user and request.user.role == "User":
            return True
        return False
