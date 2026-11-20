import django_filters

from parts.models import Category, Location, Part


NO_LOCATION = 'none'


def grouped_categories(root_label='{} — все'):
    """Choices for a <select>: a root without children is an option, a root
    with children is an optgroup of itself plus its children."""
    choices = []
    roots = Category.objects.filter(parent=None).prefetch_related('children')
    for root in roots:
        children = list(root.children.all())
        if not children:
            choices.append((root.pk, root.name))
            continue
        group = [(root.pk, root_label.format(root.name))]
        group += [(child.pk, child.name) for child in children]
        choices.append((root.name, group))
    return choices


class PartFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_q',
        label='Поиск',
        help_text='Слова через пробел; каждое ищется в названии, номинале, '
                  'корпусе, производителе, артикуле, описании и заметках.',
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        method='filter_category',
        label='Категория',
        help_text='ID категории; верхняя категория включает подкатегории.',
    )
    location = django_filters.CharFilter(
        method='filter_location',
        label='Место',
        help_text=f'ID места или «{NO_LOCATION}» — место не указано.',
    )
    mounting = django_filters.ChoiceFilter(
        choices=Part.Mounting.choices,
        label='Монтаж',
    )
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='В наличии',
        help_text='true — количество больше нуля, false — ноль.',
    )

    class Meta:
        model = Part
        fields = ['q', 'category', 'location', 'mounting', 'in_stock']

    def filter_q(self, queryset, name, value):
        return queryset.search(value)

    def filter_category(self, queryset, name, value):
        return queryset.in_category(value)

    def filter_location(self, queryset, name, value):
        if value == NO_LOCATION:
            return queryset.filter(location=None)
        if not value.isdigit():
            return queryset.none()
        return queryset.filter(location_id=int(value))

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(quantity__gt=0)
        return queryset.filter(quantity=0)


def location_choices():
    return ([(NO_LOCATION, '— не указано —')]
            + [(loc.pk, loc.name) for loc in Location.objects.all()])
