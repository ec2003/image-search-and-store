from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions


def health(_request):
    return JsonResponse({"status": "ok"})


api_v1_patterns = [
    re_path(r"^api/(?P<version>v1)/", include("image.urls")),
]

schema_view = get_schema_view(
    openapi.Info(
        title="Image Search and Store API",
        default_version="v1",
        description="API for storing inventory images and searching them with image embeddings.",
    ),
    public=True,
    permission_classes=(permissions.IsAdminUser,),
    patterns=api_v1_patterns,
)

urlpatterns = [
    path("", TemplateView.as_view(template_name="image/home.html"), name="home"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    *api_v1_patterns,
    path("api/", include("image.urls")),
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
