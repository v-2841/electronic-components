from django.contrib.auth.decorators import login_required
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from api import views


router = views.Router()
router.register('categories', views.CategoryViewSet)
router.register('locations', views.LocationViewSet)
router.register('parts', views.PartViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('guide/', views.GuideView.as_view(), name='api-guide'),
    path('token/', views.TokenView.as_view(), name='api-token'),
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/', login_required(
        SpectacularSwaggerView.as_view(url_name='api-schema')),
        name='api-docs'),
]
