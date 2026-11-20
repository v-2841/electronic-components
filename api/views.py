from django.db.models import Count, ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from api.serializers import (AdjustSerializer, CategorySerializer,
                             LocationSerializer, PartSerializer)
from parts.filters import PartFilter
from parts.models import Category, Location, Part


class Pagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 1000


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'protected'


class CategoryViewSet(viewsets.ModelViewSet):
    """Категории: два уровня, `parent` — ID верхней категории или null.
    `parts_count` — детали прямо в этой категории (без подкатегорий)."""

    queryset = (Category.objects.select_related('parent')
                .annotate(parts_count=Count('parts'))
                .order_by('parent__name', 'name'))
    serializer_class = CategorySerializer
    pagination_class = None
    filterset_fields = ['parent']
    ordering_fields = ['name']

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise Conflict('В категории есть детали или подкатегории.')


class LocationViewSet(viewsets.ModelViewSet):
    """Места хранения. При удалении места у его деталей место становится
    null («не указано»)."""

    queryset = Location.objects.annotate(parts_count=Count('parts'))
    serializer_class = LocationSerializer
    pagination_class = None
    ordering_fields = ['name']


class PartViewSet(viewsets.ModelViewSet):
    """Детали. Фото загружается multipart-запросом (поле `photo`)."""

    queryset = Part.objects.select_related('category__parent', 'location')
    serializer_class = PartSerializer
    pagination_class = Pagination
    filterset_class = PartFilter
    ordering_fields = ['name', 'quantity', 'created_at', 'updated_at']
    ordering = ['name']

    @extend_schema(request=AdjustSerializer, responses=PartSerializer)
    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """Изменить количество на `delta` одним запросом к базе: два
        одновременных изменения не затирают друг друга."""
        part = self.get_object()
        serializer = AdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        part.adjust_quantity(serializer.validated_data['delta'])
        return Response(self.get_serializer(part).data)
