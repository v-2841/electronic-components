from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from parts.models import Category, Location, Part


class CategorySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        source='__str__',
        read_only=True,
    )
    parts_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'parent', 'full_name', 'parts_count']

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
    )

    class Meta:
        model = Location
        fields = ['id', 'name', 'description', 'parts_count']


class PartSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source='category.__str__',
        read_only=True,
    )
    location_name = serializers.CharField(
        source='location.name',
        read_only=True,
        default=None,
    )
    photo = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text='Файл картинки (multipart/form-data); null — убрать фото.',
    )

    class Meta:
        model = Part
        fields = ['id', 'name', 'category', 'category_name', 'value',
                  'package', 'mounting', 'manufacturer', 'part_number',
                  'description', 'quantity', 'unit', 'location',
                  'location_name', 'photo', 'datasheet_url', 'product_url',
                  'notes', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class AdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField(
        help_text='Сколько добавить (отрицательное — списать). Ниже нуля '
                  'количество не опускается.',
    )
