from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, Prefetch, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import (CreateView, DeleteView, DetailView,
                                  ListView, UpdateView)

from parts.filters import PartFilter
from parts.forms import CategoryForm, LocationForm, PartForm, PartSearchForm
from parts.models import Category, Location, Part


# keys match parts.forms.SORT_CHOICES
SORTS = {
    'name': ['name'],
    '-quantity': ['-quantity', 'name'],
    'quantity': ['quantity', 'name'],
    '-updated': ['-updated_at'],
}


class PartListView(LoginRequiredMixin, ListView):
    template_name = 'parts/part_list.html'
    paginate_by = 50

    def get_queryset(self):
        self.filterset = PartFilter(
            self.request.GET,
            queryset=Part.objects.select_related('category__parent',
                                                 'location'))
        self.sort = self.request.GET.get('sort', 'name')
        if self.sort not in SORTS:
            self.sort = 'name'
        return self.filterset.qs.order_by(*SORTS[self.sort])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update({
            'params': params.urlencode(),
            'search_form': PartSearchForm(self.request.GET),
            'filtered': any(self.request.GET.get(key)
                            for key in PartFilter.Meta.fields),
        })
        return context


class PartDetailView(LoginRequiredMixin, DetailView):
    model = Part
    queryset = Part.objects.select_related('category__parent', 'location')


class FormPageMixin(LoginRequiredMixin, SuccessMessageMixin):
    template_name = 'form.html'
    title_new = ''

    def get_cancel_url(self):
        return self.success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title_new'] = self.title_new
        context['cancel_url'] = self.get_cancel_url()
        return context


class PartFormMixin(FormPageMixin):
    model = Part
    form_class = PartForm
    title_new = 'Новая деталь'

    def get_cancel_url(self):
        if self.object and self.object.pk:
            return self.object.get_absolute_url()
        return reverse('parts:list')


class PartCreateView(PartFormMixin, CreateView):
    success_message = 'Деталь «%(name)s» добавлена.'

    def get_initial(self):
        initial = super().get_initial()
        for key in ('category', 'location'):
            if self.request.GET.get(key, '').isdigit():
                initial[key] = self.request.GET[key]
        return initial


class PartUpdateView(PartFormMixin, UpdateView):
    success_message = 'Деталь «%(name)s» сохранена.'


class DeletePageMixin(LoginRequiredMixin):
    template_name = 'confirm_delete.html'
    protected_message = ''
    warning = ''

    def get_cancel_url(self):
        return self.success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        context['warning'] = self.warning
        return context

    def form_valid(self, form):
        name = str(self.object)
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.protected_message)
            return redirect(self.get_cancel_url())
        messages.success(self.request, f'«{name}» удалено.')
        return response


class PartDeleteView(DeletePageMixin, DeleteView):
    model = Part
    success_url = reverse_lazy('parts:list')

    def get_cancel_url(self):
        return self.object.get_absolute_url()


@login_required
@require_POST
def adjust_quantity(request, pk):
    part = get_object_or_404(Part, pk=pk)
    value = request.POST.get('quantity', '').strip()
    delta = request.POST.get('delta', '').strip()
    if value.isdigit():
        part.adjust_quantity(int(value) - part.quantity)
    elif delta.lstrip('-').isdigit():
        part.adjust_quantity(int(delta))
    else:
        messages.error(request, 'Количество — целое число не меньше нуля.')
    target = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        target = reverse('parts:detail', args=[part.pk])
    return redirect(f'{target}#part-{part.pk}')


class CategoryListView(LoginRequiredMixin, ListView):
    template_name = 'parts/category_list.html'

    def get_queryset(self):
        children = Category.objects.annotate(count=Count('parts'))
        roots = list(Category.objects.filter(parent=None)
                     .annotate(count=Count('parts'))
                     .prefetch_related(Prefetch('children', children)))
        for root in roots:
            root.total = root.count + sum(
                child.count for child in root.children.all())
        return roots


class CategoryFormMixin(FormPageMixin):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy('parts:categories')
    title_new = 'Новая категория'


class CategoryCreateView(CategoryFormMixin, CreateView):
    success_message = 'Категория «%(name)s» добавлена.'

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('parent', '').isdigit():
            initial['parent'] = self.request.GET['parent']
        return initial


class CategoryUpdateView(CategoryFormMixin, UpdateView):
    success_message = 'Категория «%(name)s» сохранена.'


class CategoryDeleteView(DeletePageMixin, DeleteView):
    model = Category
    success_url = reverse_lazy('parts:categories')
    protected_message = ('Категорию нельзя удалить: в ней есть детали '
                         'или подкатегории.')


class LocationListView(LoginRequiredMixin, ListView):
    template_name = 'parts/location_list.html'

    def get_queryset(self):
        return Location.objects.annotate(
            count=Count('parts'),
            in_stock=Count('parts', filter=Q(parts__quantity__gt=0)))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unsorted'] = Part.objects.filter(location=None).count()
        return context


class LocationFormMixin(FormPageMixin):
    model = Location
    form_class = LocationForm
    success_url = reverse_lazy('parts:locations')
    title_new = 'Новое место хранения'


class LocationCreateView(LocationFormMixin, CreateView):
    success_message = 'Место «%(name)s» добавлено.'


class LocationUpdateView(LocationFormMixin, UpdateView):
    success_message = 'Место «%(name)s» сохранено.'


class LocationDeleteView(DeletePageMixin, DeleteView):
    model = Location
    success_url = reverse_lazy('parts:locations')
    warning = ('Детали из этого места останутся, у них будет «место '
               'не указано».')
