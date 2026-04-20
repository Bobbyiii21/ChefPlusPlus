from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home.index'),
    path('about/', views.about, name='home.about'),
    path('chat/', views.chat, name='home.chat'),
    path('chat/api/', views.chat_api, name='home.chat_api'),
]