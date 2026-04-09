from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path('', views.index, name='home.index'),
    path('about', views.about, name='home.about'),
    path('api/chat', api_views.chat_api, name='home.chat_api'),
]