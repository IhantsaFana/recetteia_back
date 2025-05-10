from rest_framework import serializers
from .models import Recipe

class RecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = [
            'id', 'title', 'ingredients', 'steps', 'cuisine_type',
            'language', 'duration', 'created_at', 'rating',
            'ratings_count', 'tags', 'difficulty', 'image_url'
        ]