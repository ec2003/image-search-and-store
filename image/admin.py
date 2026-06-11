from django.contrib import admin

from .models import ImageAsset


@admin.register(ImageAsset)
class ImageAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "owner", "visibility", "status", "content_type", "size_bytes", "created_at")
    list_filter = ("status", "visibility", "content_type", "created_at")
    search_fields = ("id", "filename", "object_key", "owner__username", "tags")
    readonly_fields = ("id", "created_at", "updated_at", "indexed_at")
