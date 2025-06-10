from rest_framework.permissions import BasePermission

class IsAdminOrInstructor(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return request.user.is_superuser or request.user.role == "instructor"
        return False

class IsAdminOrStudent(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return request.user.is_superuser or request.user.role == "student"
        return False

class IsAdminUserAlwaysAllow(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser
