from django.urls import path
from .views import RecipeListView, GenerateRecipeView, RecipeDetailView

urlpatterns = [
    path('recipes/', RecipeListView.as_view(), name='recipe-list'),
    path('recipes/generate/', GenerateRecipeView.as_view(), name='recipe-generate'),
    path('recipes/<int:recipe_id>/', RecipeDetailView.as_view(), name='recipe-detail'),
]