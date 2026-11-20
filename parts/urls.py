from django.urls import path

from parts import views


app_name = 'parts'

urlpatterns = [
    path('', views.PartListView.as_view(), name='list'),
    path('parts/new/', views.PartCreateView.as_view(), name='create'),
    path('parts/<int:pk>/', views.PartDetailView.as_view(), name='detail'),
    path('parts/<int:pk>/edit/', views.PartUpdateView.as_view(),
         name='update'),
    path('parts/<int:pk>/delete/', views.PartDeleteView.as_view(),
         name='delete'),
    path('parts/<int:pk>/adjust/', views.adjust_quantity, name='adjust'),
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('categories/new/', views.CategoryCreateView.as_view(),
         name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(),
         name='category_update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(),
         name='category_delete'),
    path('locations/', views.LocationListView.as_view(), name='locations'),
    path('locations/new/', views.LocationCreateView.as_view(),
         name='location_create'),
    path('locations/<int:pk>/edit/', views.LocationUpdateView.as_view(),
         name='location_update'),
    path('locations/<int:pk>/delete/', views.LocationDeleteView.as_view(),
         name='location_delete'),
]
