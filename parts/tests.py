import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from parts.models import Category, Location, Part


MEDIA = tempfile.mkdtemp()


def image_file(name='photo.png', size=(2000, 1000)):
    buffer = BytesIO()
    Image.new('RGB', size, 'red').save(buffer, 'PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), 'image/png')


@override_settings(MEDIA_ROOT=MEDIA)
class PagesTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('v', password='pw')
        cls.res = Category.objects.create(name='Резисторы')
        cls.tht = Category.objects.create(name='Выводные', parent=cls.res)
        cls.diodes = Category.objects.create(name='Диоды')
        cls.box = Location.objects.create(name='Органайзер 1 / A3')
        cls.r1k = Part.objects.create(
            name='Резистор 1 кОм 0.25 Вт', category=cls.tht, value='1 кОм',
            quantity=5, location=cls.box)
        cls.diode = Part.objects.create(
            name='1N4007', category=cls.diodes, package='DO-41')

    def setUp(self):
        self.client.force_login(self.user)

    def list_names(self, **params):
        response = self.client.get(reverse('parts:list'), params)
        self.assertEqual(response.status_code, 200)
        return [p.name for p in response.context['object_list']]

    def test_login_required(self):
        self.client.logout()
        for name in ('parts:list', 'parts:categories', 'parts:locations',
                     'parts:create'):
            response = self.client.get(reverse(name))
            self.assertRedirects(
                response, f'{reverse("login")}?next={reverse(name)}')

    def test_login_page(self):
        self.client.logout()
        response = self.client.post(reverse('login'),
                                    {'username': 'v', 'password': 'pw'})
        self.assertRedirects(response, reverse('parts:list'))

    def test_list_filters(self):
        self.assertEqual(self.list_names(), ['1N4007',
                                             'Резистор 1 кОм 0.25 Вт'])
        self.assertEqual(self.list_names(q='РЕЗИСТОР ком'),
                         ['Резистор 1 кОм 0.25 Вт'])
        self.assertEqual(self.list_names(category=self.res.pk),
                         ['Резистор 1 кОм 0.25 Вт'])
        self.assertEqual(self.list_names(location='none'), ['1N4007'])
        self.assertEqual(self.list_names(location=self.box.pk),
                         ['Резистор 1 кОм 0.25 Вт'])
        self.assertEqual(self.list_names(in_stock='false'), ['1N4007'])
        self.assertEqual(self.list_names(sort='-quantity')[0],
                         'Резистор 1 кОм 0.25 Вт')
        self.assertEqual(self.list_names(category='junk', sort='junk'),
                         ['1N4007', 'Резистор 1 кОм 0.25 Вт'])

    def test_list_renders_grouped_category_select(self):
        response = self.client.get(reverse('parts:list'),
                                   {'category': self.tht.pk})
        self.assertContains(response, '<optgroup label="Резисторы">')
        self.assertContains(
            response, f'<option value="{self.tht.pk}" selected>Выводные')
        self.assertContains(response, f'<option value="{self.diodes.pk}">'
                                      'Диоды</option>')

    def test_adjust(self):
        url = reverse('parts:adjust', args=[self.r1k.pk])
        next_url = reverse('parts:list') + '?q=1'
        response = self.client.post(url, {'delta': '-2', 'next': next_url})
        self.assertRedirects(response, f'{next_url}#part-{self.r1k.pk}',
                             fetch_redirect_response=False)
        self.r1k.refresh_from_db()
        self.assertEqual(self.r1k.quantity, 3)
        self.client.post(url, {'delta': '-100'})
        self.r1k.refresh_from_db()
        self.assertEqual(self.r1k.quantity, 0)
        self.client.post(url, {'quantity': '42'})
        self.r1k.refresh_from_db()
        self.assertEqual(self.r1k.quantity, 42)
        response = self.client.post(url, {'quantity': '-1'}, follow=True)
        self.assertContains(response, 'целое число')
        self.r1k.refresh_from_db()
        self.assertEqual(self.r1k.quantity, 42)

    def test_adjust_ignores_foreign_next(self):
        response = self.client.post(
            reverse('parts:adjust', args=[self.r1k.pk]),
            {'delta': '1', 'next': 'https://evil.example/'})
        self.assertRedirects(
            response, f'{self.r1k.get_absolute_url()}#part-{self.r1k.pk}',
            fetch_redirect_response=False)

    def test_adjust_needs_post(self):
        response = self.client.get(reverse('parts:adjust',
                                           args=[self.r1k.pk]))
        self.assertEqual(response.status_code, 405)

    def test_create_with_photo_and_edit(self):
        response = self.client.post(reverse('parts:create'), {
            'name': 'BC557C', 'category': self.diodes.pk, 'quantity': '2',
            'unit': 'pcs', 'photo': image_file()})
        part = Part.objects.get(name='BC557C')
        self.assertRedirects(response, part.get_absolute_url())
        self.assertTrue(part.photo.name.endswith('.jpg'))
        self.assertEqual(Image.open(part.photo.path).size, (1600, 800))
        response = self.client.get(part.get_absolute_url())
        self.assertContains(response, part.photo.url)
        response = self.client.post(
            reverse('parts:update', args=[part.pk]),
            {'name': 'BC557C', 'category': self.diodes.pk,
             'quantity': '7', 'unit': 'pcs', 'location': self.box.pk})
        part.refresh_from_db()
        self.assertEqual((part.quantity, part.location), (7, self.box))

    def test_forms_render(self):
        for url in (reverse('parts:create'),
                    reverse('parts:update', args=[self.r1k.pk]),
                    reverse('parts:delete', args=[self.r1k.pk]),
                    reverse('parts:category_create'),
                    reverse('parts:category_update', args=[self.tht.pk]),
                    reverse('parts:location_create'),
                    reverse('parts:location_delete', args=[self.box.pk]),
                    self.r1k.get_absolute_url(),
                    reverse('parts:categories'),
                    reverse('parts:locations')):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_category_parent_choices_are_roots(self):
        response = self.client.get(reverse('parts:category_update',
                                           args=[self.res.pk]))
        parents = list(response.context['form'].fields['parent'].queryset)
        self.assertEqual(parents, [self.diodes])
        response = self.client.post(reverse('parts:category_create'), {
            'name': 'Третий', 'parent': self.tht.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Category.objects.filter(name='Третий').exists())

    def test_category_delete_protected(self):
        response = self.client.post(
            reverse('parts:category_delete', args=[self.res.pk]),
            follow=True)
        self.assertContains(response, 'нельзя удалить')
        self.assertTrue(Category.objects.filter(pk=self.res.pk).exists())

    def test_location_delete_keeps_parts(self):
        self.client.post(reverse('parts:location_delete',
                                 args=[self.box.pk]))
        self.r1k.refresh_from_db()
        self.assertIsNone(self.r1k.location)

    def test_part_delete(self):
        response = self.client.post(reverse('parts:delete',
                                            args=[self.diode.pk]))
        self.assertRedirects(response, reverse('parts:list'))
        self.assertFalse(Part.objects.filter(pk=self.diode.pk).exists())
