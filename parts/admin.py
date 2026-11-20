from django.contrib import admin

from parts.models import Category, Location, Part


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'parent']
    list_filter = ['parent']
    ordering = ['parent__name', 'name']


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['name', 'value', 'package', 'category', 'quantity',
                    'unit', 'location']
    list_filter = ['category__parent', 'category', 'mounting', 'location']
    list_select_related = ['category__parent', 'location']
    search_fields = ['name']

    # the default search (icontains) misses Cyrillic case on SQLite
    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return queryset, False
        return queryset.search(search_term), False
