from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='developer.index'),
    path('files', views.database_files, name='developer.files'),
    path('files/delete/<int:file_id>', views.delete_database_file, name='developer.files.delete'),
    path('api/clean-text', views.clean_text_api, name='developer.api.clean_text'),
    path('logs', views.usage_logs, name='developer.logs'),
    path(
        'api/suggest-description',
        views.suggest_description_api,
        name='developer.api.suggest_description',
    ),
]
