from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models.functions import Greatest, Least
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps


PHOTO_MAX_SIDE = 1600
MAX_QUANTITY = 2147483647   # PositiveIntegerField range
SEARCH_FIELDS = ['name', 'value', 'package', 'manufacturer', 'part_number',
                 'description', 'notes']


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name='Название',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория',
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(parent__isnull=True),
                name='unique_root_category_name',
            ),
            models.UniqueConstraint(
                fields=['parent', 'name'],
                name='unique_category_name_in_parent',
            ),
        ]
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        if self.parent_id:
            return f'{self.parent.name} / {self.name}'
        return self.name

    def clean(self):
        if self.parent_id is None:
            return
        if self.pk and self.parent_id == self.pk:
            raise ValidationError(
                {'parent': 'Категория не может быть родителем самой себе.'})
        # from the base, not self.parent: that object may be read before
        # another request moved the parent (see save)
        grandparent = (Category.objects.filter(pk=self.parent_id)
                       .values_list('parent_id', flat=True).first())
        if grandparent is not None:
            raise ValidationError(
                {'parent': 'Родителем может быть только категория '
                           'верхнего уровня.'})
        if self.pk and self.children.exists():
            raise ValidationError(
                {'parent': 'У категории есть подкатегории, поэтому она '
                           'не может стать подкатегорией.'})

    # check and write in one transaction (SQLite IMMEDIATE mode, see
    # settings): two requests validated at once cannot build a third level
    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.clean()
            super().save(*args, **kwargs)


class Location(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название',
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Место хранения'
        verbose_name_plural = 'Места хранения'

    def __str__(self):
        return self.name


class PartQuerySet(models.QuerySet):
    # every word of the query must be found in one of SEARCH_FIELDS,
    # case-insensitive for Cyrillic too (see parts/lookups.py)
    def search(self, query):
        queryset = self
        for word in query.lower().split():
            condition = models.Q()
            for field in SEARCH_FIELDS:
                condition |= models.Q(**{f'{field}__ulower__contains': word})
            queryset = queryset.filter(condition)
        return queryset

    # a top-level category includes its subcategories
    def in_category(self, category):
        return self.filter(models.Q(category=category)
                           | models.Q(category__parent=category))


class Part(models.Model):
    class Mounting(models.TextChoices):
        THT = 'tht', 'Выводной'
        SMD = 'smd', 'SMD'

    class Unit(models.TextChoices):
        PIECE = 'pcs', 'шт'
        METER = 'm', 'м'

    name = models.CharField(
        max_length=200,
        verbose_name='Название',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='parts',
        verbose_name='Категория',
    )
    value = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Номинал',
    )
    package = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Корпус',
    )
    mounting = models.CharField(
        max_length=3,
        choices=Mounting,
        blank=True,
        verbose_name='Монтаж',
    )
    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Производитель',
    )
    part_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Артикул',
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание',
    )
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество',
    )
    unit = models.CharField(
        max_length=3,
        choices=Unit,
        default=Unit.PIECE,
        verbose_name='Единица',
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parts',
        verbose_name='Место',
    )
    photo = models.ImageField(
        upload_to='parts/',
        blank=True,
        verbose_name='Фото',
    )
    datasheet_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Даташит',
    )
    product_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Ссылка на товар',
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Заметки',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Изменено',
    )

    objects = PartQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        verbose_name = 'Деталь'
        verbose_name_plural = 'Детали'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('parts:detail', args=[self.pk])

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        old_photo = None
        if self.pk and (update_fields is None or 'photo' in update_fields):
            old_photo = (Part.objects.filter(pk=self.pk)
                         .values_list('photo', flat=True).first())
        if self.photo and not self.photo._committed:
            self.photo = shrink_photo(self.photo)
        super().save(*args, **kwargs)
        if old_photo and old_photo != self.photo.name:
            forget_photo(old_photo)

    # quantity changes are single UPDATEs, never read-modify-write: a
    # concurrent ± is not lost; update() skips auto_now, so updated_at too
    def adjust_quantity(self, delta):
        new = Greatest(models.F('quantity') + delta, 0)
        Part.objects.filter(pk=self.pk).update(
            quantity=Least(new, MAX_QUANTITY), updated_at=timezone.now())
        self.refresh_from_db(fields=['quantity', 'updated_at'])

    def set_quantity(self, value):
        Part.objects.filter(pk=self.pk).update(
            quantity=value, updated_at=timezone.now())
        self.refresh_from_db(fields=['quantity', 'updated_at'])


# the old file goes after the commit, and only if no part still uses it
def forget_photo(name):
    def delete_if_unused():
        if not Part.objects.filter(photo=name).exists():
            Part._meta.get_field('photo').storage.delete(name)
    transaction.on_commit(delete_if_unused)


@receiver(post_delete, sender=Part)
def delete_photo_file(sender, instance, **kwargs):
    if instance.photo:
        forget_photo(instance.photo.name)


# phone photos are megabytes: keep at most PHOTO_MAX_SIDE px, as JPEG
def shrink_photo(photo):
    image = Image.open(photo)
    rotated = image.getexif().get(0x0112, 1) != 1
    if (image.format == 'JPEG' and not rotated
            and max(image.size) <= PHOTO_MAX_SIDE):
        photo.seek(0)
        return photo
    image = ImageOps.exif_transpose(image)
    image.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
    out = BytesIO()
    image.convert('RGB').save(out, 'JPEG', quality=85)
    name = photo.name.rsplit('.', 1)[0] + '.jpg'
    return ContentFile(out.getvalue(), name=name.rsplit('/', 1)[-1])
