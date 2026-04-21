from django.db import models
from django.utils import timezone
from accounts.models import CPPUser
import os

def get_recipe_image_path(recipe, filename):
    """Generate file path for recipe images"""
    filetype = filename.split('.')[-1]
    new_name = f"recipe_{recipe.id}.{filetype}"
    return os.path.join('recipes', new_name)


class Recipe(models.Model):
    user = models.ForeignKey(CPPUser, on_delete=models.CASCADE, related_name='recipes')
    title = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(upload_to=get_recipe_image_path, blank=True, null=True, help_text="Optional image of the recipe")
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Recipe'
        verbose_name_plural = 'Recipes'
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
