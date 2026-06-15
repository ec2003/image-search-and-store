from django.urls import path

from images.api.v1.views import ImageViewSet

urlpatterns = [
    path("images/", ImageViewSet.as_view({"get": "list"}), name="image-list"),
    path("images/upload/", ImageViewSet.as_view({"post": "upload"}), name="image-upload"),
    path("images/search/", ImageViewSet.as_view({"post": "search"}), name="image-search"),
    path("images/<uuid:pk>/", ImageViewSet.as_view({"get": "retrieve"}), name="image-detail"),
]
