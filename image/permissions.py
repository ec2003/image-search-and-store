from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import ImageVisibility


class IsOwnerOrPublicReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.owner_id == request.user.id:
            return True
        return (
            request.method in SAFE_METHODS
            and obj.visibility == ImageVisibility.PUBLIC
            and obj.is_searchable
        )
