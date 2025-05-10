from django.contrib import admin
from .models import Recipe

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('title', 'cuisine_type', 'language', 'duration', 'created_at')
    list_filter = ('cuisine_type', 'language', 'created_at')
    search_fields = ('title', 'ingredients', 'steps')
    readonly_fields = ('created_at',)
