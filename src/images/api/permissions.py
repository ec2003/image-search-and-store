from rest_framework.permissions import BasePermission


class IsAdminUserForDocs(BasePermission):
    """
    Custom permission to only allow admin/staff users to access Swagger docs.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )