from django.views.generic import ListView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from .models import Recipe


class RecipeListView(LoginRequiredMixin, ListView):
    """Display all recipes saved by the current user"""
    model = Recipe
    template_name = 'recipes/index.html'
    context_object_name = 'recipes'
    paginate_by = 12
    
    def get_queryset(self):
        return Recipe.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template_data'] = {
            'title': 'My Recipes',
            'total_recipes': self.get_queryset().count()
        }
        return context


class RecipeDetailView(LoginRequiredMixin, DetailView):
    """Display a single recipe"""
    model = Recipe
    template_name = 'recipes/detail.html'
    context_object_name = 'recipe'
    
    def get_queryset(self):
        # Only allow users to view their own recipes
        return Recipe.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template_data'] = {
            'title': self.object.title
        }
        return context


class RecipeUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing recipe"""
    model = Recipe
    template_name = 'recipes/form.html'
    fields = ['title', 'content', 'image']
    
    def get_queryset(self):
        # Only allow users to edit their own recipes
        return Recipe.objects.filter(user=self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('recipes.detail', kwargs={'pk': self.object.pk})


class RecipeDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a recipe"""
    model = Recipe
    template_name = 'recipes/confirm_delete.html'
    success_url = reverse_lazy('recipes.index')
    
    def get_queryset(self):
        # Only allow users to delete their own recipes
        return Recipe.objects.filter(user=self.request.user)
