import json
from pathlib import Path

from django.db.models import Count, ProtectedError
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (OpenApiExample, extend_schema,
                                   extend_schema_view)
from rest_framework import status, viewsets
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.pagination import PageNumberPagination
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse as drf_reverse
from rest_framework.routers import APIRootView, DefaultRouter
from rest_framework.views import APIView

from api.serializers import (AdjustSerializer, CategorySerializer,
                             LocationSerializer, PartSerializer)
from parts.filters import PartFilter
from parts.models import Category, Location, Part


GUIDE = Path(__file__).with_name('guide.md')


class ApiRootView(APIRootView):
    """Радиодетали API. ИИ-агентам: сначала прочитайте `guide`."""

    # the guide and the schema first: an agent given only this address
    # must find them without guessing
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        links = {name: drf_reverse(f'api-{name}', request=request)
                 for name in ('guide', 'schema', 'docs', 'token')}
        response.data = {**links, **response.data}
        return response


class Router(DefaultRouter):
    APIRootView = ApiRootView


class Pagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 1000


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'protected'


# the response of POST/PUT/PATCH carries parts_count like GET does
class AnnotatedResponseMixin:
    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance = self.get_queryset().get(
            pk=serializer.instance.pk)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        serializer.instance = self.get_queryset().get(
            pk=serializer.instance.pk)


def crud_schema(one, many):
    return extend_schema_view(
        list=extend_schema(summary=f'Список: {many}'),
        create=extend_schema(summary=f'Создать: {one}'),
        retrieve=extend_schema(summary=f'Получить: {one}'),
        update=extend_schema(summary=f'Заменить целиком: {one}'),
        partial_update=extend_schema(
            summary=f'Изменить отдельные поля: {one}'),
        destroy=extend_schema(summary=f'Удалить: {one}'),
    )


@crud_schema('категория', 'категории')
class CategoryViewSet(AnnotatedResponseMixin, viewsets.ModelViewSet):
    """Категории — дерево в два уровня: верхняя («Диоды») и подкатегории
    («Шоттки»). Список отдаётся целиком, без страниц."""

    # with subcategories, as the parts filter `category=<id>` counts them
    queryset = (Category.objects.select_related('parent')
                .annotate(parts_count=Count('parts', distinct=True)
                          + Count('children__parts', distinct=True))
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


@crud_schema('место хранения', 'места хранения')
class LocationViewSet(AnnotatedResponseMixin, viewsets.ModelViewSet):
    """Места хранения — плоский список коробок и ячеек. При удалении места
    у его деталей место становится null («не указано»)."""

    queryset = Location.objects.annotate(parts_count=Count('parts'))
    serializer_class = LocationSerializer
    pagination_class = None
    ordering_fields = ['name']


@crud_schema('деталь', 'детали')
@extend_schema_view(
    create=extend_schema(examples=[OpenApiExample(
        'Новая деталь',
        request_only=True,
        value={
            'name': 'Резистор 10 кОм 0.25 Вт',
            'category': 2,
            'value': '10 кОм',
            'package': 'Аксиальный',
            'mounting': 'tht',
            'quantity': 20,
            'unit': 'pcs',
            'location': None,
        },
    )]),
)
class PartViewSet(viewsets.ModelViewSet):
    """Детали. Перед созданием ищите существующую (`?q=`), чтобы не
    плодить дубли. Фото загружается multipart-запросом (поле `photo`)."""

    queryset = Part.objects.select_related('category__parent', 'location')
    serializer_class = PartSerializer
    pagination_class = Pagination
    filterset_class = PartFilter
    ordering_fields = ['name', 'quantity', 'created_at', 'updated_at']
    ordering = ['name']

    @extend_schema(
        summary='Прибавить или списать количество',
        request=AdjustSerializer,
        responses=PartSerializer,
        examples=[
            OpenApiExample('Списать 2', value={'delta': -2},
                           request_only=True),
            OpenApiExample('Прибавить 10', value={'delta': 10},
                           request_only=True),
        ],
    )
    @action(detail=True, methods=['post'])
    def adjust(self, request, pk=None):
        """Изменить количество на `delta` одним запросом к базе: два
        одновременных изменения не затирают друг друга, ниже нуля
        количество не опускается. Точное число после пересчёта — PATCH
        поля `quantity`."""
        part = self.get_object()
        serializer = AdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        part.adjust_quantity(serializer.validated_data['delta'])
        return Response(self.get_serializer(part).data)


@extend_schema_view(post=extend_schema(
    auth=[],
    summary='Получить токен по логину и паролю',
    description='Тело: `username`, `password` (форма или JSON). Ответ: '
                '`{"token": "..."}`; дальше заголовок '
                '`Authorization: Token <токен>`. У пользователя один '
                'токен — повторный запрос вернёт тот же.',
))
class TokenView(ObtainAuthToken):
    pass


class MarkdownRenderer(BaseRenderer):
    media_type = 'text/markdown'
    format = 'md'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if not isinstance(data, str):   # errors: {'detail': ...}
            data = json.dumps(data, ensure_ascii=False)
        return data.encode(self.charset)


# the guide is markdown whatever the client accepts (text/plain, */*, ...)
class AlwaysFirstRenderer(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class GuideView(APIView):
    renderer_classes = [MarkdownRenderer]
    content_negotiation_class = AlwaysFirstRenderer

    @extend_schema(
        summary='Инструкция для ИИ-агентов',
        description='Markdown: доступ, модель данных, типовые задачи, '
                    'правила. Агенту — прочитать первым.',
        responses={(200, 'text/markdown'): OpenApiTypes.STR},
    )
    def get(self, request):
        return Response(GUIDE.read_text(encoding='utf-8').replace(
            '{{BASE}}', request.build_absolute_uri(reverse('api-root'))))
