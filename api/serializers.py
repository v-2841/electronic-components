from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from parts.models import Category, Location, Part


class CategorySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        source='__str__',
        read_only=True,
        help_text='Полное имя: «Диоды / Шоттки» или «Модули».',
    )
    parts_count = serializers.IntegerField(
        read_only=True,
        help_text='Сколько деталей (записей) в категории вместе с '
                  'подкатегориями — столько же вернёт '
                  '/api/v1/parts/?category=<id>.',
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'parent', 'full_name', 'parts_count']
        extra_kwargs = {
            'name': {
                'help_text': 'Название: «Шоттки», «Резисторы».',
            },
            'parent': {
                'help_text': 'ID верхней категории или null, если категория '
                             'сама верхняя. Глубина — не больше двух уровней.',
            },
        }

    # model rules (two levels at most) live in Category.clean()
    def validate(self, attrs):
        category = Category(pk=getattr(self.instance, 'pk', None))
        category.name = attrs.get('name', getattr(self.instance, 'name', ''))
        category.parent = attrs.get(
            'parent', getattr(self.instance, 'parent', None))
        try:
            category.clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict)
        return attrs


class LocationSerializer(serializers.ModelSerializer):
    parts_count = serializers.IntegerField(
        read_only=True,
        help_text='Сколько деталей лежит в этом месте.',
    )

    class Meta:
        model = Location
        fields = ['id', 'name', 'description', 'parts_count']
        extra_kwargs = {
            'name': {
                'help_text': 'Уникальное название: «Органайзер 1 / A3».',
            },
            'description': {
                'help_text': 'Что здесь лежит или где это место.',
            },
        }


class PartSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source='category.__str__',
        read_only=True,
        help_text='Полное имя категории: «Диоды / Шоттки».',
    )
    location_name = serializers.CharField(
        source='location.name',
        read_only=True,
        default=None,
        help_text='Название места или null — место не указано.',
    )
    photo = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text='Фото: файл картинки в multipart/form-data, в ответе — '
                  'ссылка. null — убрать фото. Больше 1600 px по длинной '
                  'стороне ужимается.',
    )

    class Meta:
        model = Part
        fields = ['id', 'name', 'category', 'category_name', 'value',
                  'package', 'mounting', 'manufacturer', 'part_number',
                  'description', 'quantity', 'unit', 'location',
                  'location_name', 'photo', 'datasheet_url', 'product_url',
                  'notes', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'name': {
                'help_text': 'Название. Полупроводники, микросхемы и модули '
                             '— артикулом («IRL520NPBF», «GY-291»); пассивные '
                             '— тип, номинал, мощность или напряжение '
                             '(«Резистор 10 кОм 0.25 Вт», «Конденсатор '
                             '100 мкФ 35 В»).',
            },
            'category': {
                'help_text': 'ID категории из /api/v1/categories/; лучше '
                             'подкатегория («Диоды / Шоттки»).',
            },
            'value': {
                'help_text': 'Номинал или главные параметры, свободный '
                             'текст: «1 кОм», «0.1 мкФ, 50 В», «N, 100 В, '
                             '10 А».',
            },
            'package': {
                'help_text': 'Корпус: «TO-220», «SOT-23», «DIP-28», «0603», '
                             '«Аксиальный».',
            },
            'mounting': {
                'help_text': '«tht» — выводной, «smd» — поверхностный '
                             'монтаж, пусто — не важно (модули, провод).',
            },
            'manufacturer': {
                'help_text': 'Производитель: «Infineon», «Vishay».',
            },
            'part_number': {
                'help_text': 'Артикул производителя или серия (MPN).',
            },
            'description': {
                'help_text': 'Описание; у загруженных из счетов — строка '
                             'товара у продавца.',
            },
            'quantity': {
                'help_text': 'Сколько есть сейчас, целое число не меньше 0, '
                             'в единицах unit. Прибавить или списать — '
                             'POST /api/v1/parts/{id}/adjust/.',
            },
            'unit': {
                'help_text': '«pcs» — штуки, «m» — метры (провод, '
                             'термоусадка).',
            },
            'location': {
                'help_text': 'ID места из /api/v1/locations/ или null — место '
                             'не указано (деталь ещё не разобрана).',
            },
            'datasheet_url': {
                'help_text': 'Ссылка на даташит (PDF).',
            },
            'product_url': {
                'help_text': 'Ссылка на товар у продавца.',
            },
            'notes': {
                'help_text': 'Заметки: где и когда куплено, особенности '
                             'посадки и т. п.',
            },
            'created_at': {
                'help_text': 'Когда деталь заведена.',
            },
            'updated_at': {
                'help_text': 'Когда деталь последний раз менялась (в том '
                             'числе количество).',
            },
        }


class AdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField(
        help_text='Сколько добавить (отрицательное — списать). Ниже нуля '
                  'количество не опускается.',
    )
