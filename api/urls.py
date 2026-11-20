from django.contrib.auth.decorators import login_required
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from api import views


router = DefaultRouter()
router.register('categories', views.CategoryViewSet)
router.register('locations', views.LocationViewSet)
router.register('parts', views.PartViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('token/', obtain_auth_token, name='api-token'),
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', login_required(
        SpectacularSwaggerView.as_view(url_name='api-schema')),
        name='api-docs'),
]
