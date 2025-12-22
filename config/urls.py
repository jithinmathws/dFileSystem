from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from storage.views import StorageNodeViewSet, FileViewSet, ChunkViewSet

def health_check(request):
    """Basic health check endpoint."""
    return JsonResponse({
        "status": "ok",
        "service": "dFileSystem API",
        "version": "1.0.0"
    })

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'nodes', StorageNodeViewSet, basename='storage-node')
router.register(r'files', FileViewSet, basename='file')
router.register(r'chunks', ChunkViewSet, basename='chunk')

# API URL patterns
api_urlpatterns = [
    # API v1
    path('v1/', include([
        # Core endpoints
        path('', include(router.urls)),
        
        # Authentication
        path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        
        # Health check
        path('health/', health_check, name='health-check'),
    ]))
]

# Documentation URLs (only in development)
docs_urls = []
if settings.DEBUG:
    docs_urls = [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]

urlpatterns = [
    # Admin
    path(settings.ADMIN_URL, admin.site.urls),
    
    # API
    path('api/', include(api_urlpatterns)),
    
    # API Authentication (browsable API login)
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # Documentation (only in development)
    *docs_urls,
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers (optional but recommended)
handler400 = 'config.exceptions.bad_request'
handler403 = 'config.exceptions.permission_denied'
handler404 = 'config.exceptions.page_not_found'
handler500 = 'config.exceptions.server_error'