from django import forms
from django.core.exceptions import ValidationError

from parts.filters import grouped_categories, location_choices
from parts.models import Category, Location, Part
from parts.photos import download_photo


SORT_CHOICES = [
    ('name', 'По названию'),
    ('-quantity', 'Больше всего'),
    ('quantity', 'Меньше всего'),
    ('-updated', 'Недавно изменённые'),
]


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css = 'form-select'
            else:
                css = 'form-control'
            widget.attrs['class'] = css


# only renders the filter bar of the part list; filtering is PartFilter
class PartSearchForm(BootstrapMixin, forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'type': 'search',
            'placeholder': 'Поиск: 10 кОм, IRL520, SOT-23…',
            'aria-label': 'Поиск',
        }),
    )
    category = forms.ChoiceField(
        required=False,
    )
    location = forms.ChoiceField(
        required=False,
    )
    mounting = forms.ChoiceField(
        required=False,
        choices=[('', 'Монтаж')] + Part.Mounting.choices,
    )
    in_stock = forms.ChoiceField(
        required=False,
        choices=[('', 'Наличие'), ('true', 'Есть'), ('false', 'Нет')],
    )
    sort = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].choices = (
            [('', 'Все категории')] + grouped_categories())
        self.fields['location'].choices = (
            [('', 'Все места')] + location_choices())
        for name, field in self.fields.items():
            if name != 'q':
                field.widget.attrs['onchange'] = 'this.form.submit()'


class PartForm(BootstrapMixin, forms.ModelForm):
    photo_url = forms.URLField(
        required=False,
        assume_scheme='https',
        label='Фото по ссылке',
        help_text='Ссылка на картинку в интернете; заменит текущее фото.',
    )

    class Meta:
        model = Part
        fields = ['name', 'category', 'value', 'package', 'mounting',
                  'manufacturer', 'part_number', 'quantity', 'unit',
                  'location', 'photo', 'photo_url', 'datasheet_url',
                  'product_url', 'description', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.downloaded = None
        self.fields['category'].choices = (
            [('', '— выберите —')] + grouped_categories('{} — общее'))
        self.fields['location'].empty_label = '— не указано —'
        self.fields['mounting'].choices = (
            [('', '— не указан —')] + Part.Mounting.choices)
        # an edit form must not write back the quantity it was opened
        # with: ± in the card or the API may have changed it meanwhile
        if self.instance.pk:
            del self.fields['quantity']

    def clean(self):
        cleaned_data = super().clean()
        url = cleaned_data.get('photo_url')
        if url and self.files.get('photo'):
            self.add_error('photo_url',
                           'Фото — либо файлом, либо ссылкой, не оба сразу.')
        elif url:
            try:
                self.downloaded = download_photo(url)
            except ValidationError as error:
                self.add_error('photo_url', error)
        return cleaned_data

    def save(self, commit=True):
        part = super().save(commit=False)
        if self.downloaded:
            part.photo = self.downloaded
        if commit:
            if part.pk:   # write only what this form shows
                fields = [name for name in self.fields if name != 'photo_url']
                part.save(update_fields=fields + ['updated_at'])
            else:
                part.save()
        return part


class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        roots = Category.objects.filter(parent=None)
        if self.instance.pk:
            roots = roots.exclude(pk=self.instance.pk)
        self.fields['parent'].queryset = roots
        self.fields['parent'].empty_label = '— верхний уровень —'


class LocationForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
