from django.urls import path
from . import views

urlpatterns = [
    path('', views.news_list, name='news_list'),
    path('create/', views.news_create, name='news_create'),
    path("<uuid:pk>/", views.news_detail, name="news_detail"),
    path('edit/<uuid:pk>/', views.news_update, name='news_update'),
    path('delete/<uuid:pk>/', views.news_delete, name='news_delete'),
]
