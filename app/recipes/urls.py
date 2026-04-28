from django.urls import path
from . import views

urlpatterns = [
    path('', views.RecipeListView.as_view(), name='recipes.index'),
    path('<int:pk>/', views.RecipeDetailView.as_view(), name='recipes.detail'),
    path('<int:pk>/edit/', views.RecipeUpdateView.as_view(), name='recipes.edit'),
    path('<int:pk>/delete/', views.RecipeDeleteView.as_view(), name='recipes.delete'),
]
