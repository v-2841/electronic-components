import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from parts.models import Category, Location, Part
from parts.tests import image_file


MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class ApiTest(APITestCase):
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
        cls.box = Location.objects.create(name='Органайзер 1')
        cls.r1k = Part.objects.create(
            name='Резистор 1 кОм', category=cls.tht, quantity=5,
            location=cls.box, mounting=Part.Mounting.THT)
        cls.diode = Part.objects.create(name='1N4007', category=cls.diodes)

    def setUp(self):
        self.client.force_authenticate(self.user)

    def names(self, **params):
        response = self.client.get('/api/parts/', params)
        self.assertEqual(response.status_code, 200, response.data)
        return [p['name'] for p in response.data['results']]

    def test_auth_required(self):
        self.client.force_authenticate(None)
        for url in ('/api/parts/', '/api/categories/', '/api/locations/',
                    '/api/schema/'):
            self.assertIn(self.client.get(url).status_code, (401, 403), url)
        response = self.client.get('/api/docs/')
        self.assertRedirects(response, '/login/?next=/api/docs/')

    def test_token(self):
        self.client.force_authenticate(None)
        response = self.client.post('/api/token/',
                                    {'username': 'v', 'password': 'pw'})
        token = response.data['token']
        self.assertEqual(token, Token.objects.get(user=self.user).key)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(self.client.get('/api/parts/').status_code, 200)

    def test_part_list_and_filters(self):
        response = self.client.get('/api/parts/')
        self.assertEqual(response.data['count'], 2)
        first = response.data['results'][1]
        self.assertEqual(first['category_name'], 'Резисторы / Выводные')
        self.assertEqual(first['location_name'], 'Органайзер 1')
        self.assertEqual(self.names(q='резистор КОМ'), ['Резистор 1 кОм'])
        self.assertEqual(self.names(category=self.res.pk),
                         ['Резистор 1 кОм'])
        self.assertEqual(self.names(location='none'), ['1N4007'])
        self.assertEqual(self.names(location=self.box.pk),
                         ['Резистор 1 кОм'])
        self.assertEqual(self.names(in_stock='true'), ['Резистор 1 кОм'])
        self.assertEqual(self.names(mounting='tht'), ['Резистор 1 кОм'])
        self.assertEqual(self.names(ordering='-quantity')[0],
                         'Резистор 1 кОм')
        response = self.client.get('/api/parts/', {'page_size': 1})
        self.assertEqual(len(response.data['results']), 1)
        self.assertIsNotNone(response.data['next'])

    def test_bad_filter_value(self):
        response = self.client.get('/api/parts/', {'category': 999})
        self.assertEqual(response.status_code, 400)

    def test_part_crud(self):
        response = self.client.post('/api/parts/', {
            'name': 'BC557C', 'category': self.diodes.pk, 'quantity': 3,
            'package': 'TO-92'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertEqual(response.data['unit'], 'pcs')
        self.assertIsNone(response.data['location'])
        response = self.client.patch(f'/api/parts/{pk}/', {
            'location': self.box.pk, 'quantity': 10}, format='json')
        self.assertEqual(response.data['location_name'], 'Органайзер 1')
        self.assertEqual(response.data['quantity'], 10)
        response = self.client.patch(f'/api/parts/{pk}/', {
            'quantity': -1}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.delete(f'/api/parts/{pk}/').status_code,
                         204)

    def test_photo_upload_and_clear(self):
        url = f'/api/parts/{self.diode.pk}/'
        response = self.client.patch(url, {'photo': image_file()},
                                     format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['photo'].startswith(
            'http://testserver/media/parts/'))
        self.diode.refresh_from_db()
        self.assertTrue(self.diode.photo.name.endswith('.jpg'))
        response = self.client.patch(url, {'photo': None}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['photo'])
        self.diode.refresh_from_db()
        self.assertFalse(self.diode.photo)

    def test_adjust(self):
        url = f'/api/parts/{self.r1k.pk}/adjust/'
        response = self.client.post(url, {'delta': -2}, format='json')
        self.assertEqual(response.data['quantity'], 3)
        response = self.client.post(url, {'delta': -50}, format='json')
        self.assertEqual(response.data['quantity'], 0)
        response = self.client.post(url, {'delta': 'x'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_categories(self):
        response = self.client.get('/api/categories/')
        by_name = {c['full_name']: c for c in response.data}
        self.assertEqual(by_name['Резисторы / Выводные']['parts_count'], 1)
        response = self.client.post('/api/categories/', {
            'name': 'Третий', 'parent': self.tht.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('parent', response.data)
        response = self.client.patch(f'/api/categories/{self.res.pk}/', {
            'parent': self.diodes.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/categories/', {
            'name': 'SMD', 'parent': self.res.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        response = self.client.post('/api/categories/', {
            'name': 'SMD', 'parent': self.res.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.delete(f'/api/categories/{self.res.pk}/')
        self.assertEqual(response.status_code, 409)

    def test_locations(self):
        response = self.client.get('/api/locations/')
        self.assertEqual(response.data[0]['parts_count'], 1)
        response = self.client.delete(f'/api/locations/{self.box.pk}/')
        self.assertEqual(response.status_code, 204)
        self.r1k.refresh_from_db()
        self.assertIsNone(self.r1k.location)

    def test_docs_and_schema(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('api-docs')).status_code,
                         200)
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        call_command('spectacular', '--fail-on-warn',
                     '--file', f'{MEDIA}/schema.yml')
