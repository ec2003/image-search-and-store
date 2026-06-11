from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ImageAssetViewSet, ImageSearchView, TextSearchView

router = DefaultRouter()
router.register("images", ImageAssetViewSet, basename="image")

urlpatterns = [
    path("", include(router.urls)),
    path("search/text/", TextSearchView.as_view(), name="text-search"),
    path("search/image/", ImageSearchView.as_view(), name="image-search"),
]
