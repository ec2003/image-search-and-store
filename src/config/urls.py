"""
URL configuration for config project.
"""
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from images.api.permissions import IsAdminUserForDocs

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('images.api.v1.urls')),
    # Swagger / OpenAPI — protected by admin permission
    path('api/schema/', SpectacularAPIView.as_view(permission_classes=[IsAdminUserForDocs]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[IsAdminUserForDocs]), name='swagger-ui'),
    # Frontend
    path('', include('frontend.urls')),
]
