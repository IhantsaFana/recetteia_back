from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
import google.generativeai as genai
from .models import Recipe
from .serializers import RecipeSerializer
from .utils import search_recipe_image
import json
import time

# Configure the Gemini API with the correct model version
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

class RecipePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class RecipeListView(APIView):
    pagination_class = RecipePagination

    def get(self, request):
        # Search and filter parameters
        search_query = request.query_params.get('search', '').strip()
        cuisine_type = request.query_params.get('cuisine_type')
        language = request.query_params.get('language')
        tags = request.query_params.getlist('tags', [])
        difficulty = request.query_params.get('difficulty')
        min_rating = request.query_params.get('min_rating')

        # Get all recipes and apply filters
        recipes = Recipe.objects.all()

        # Search in title and ingredients
        if search_query:
            recipes = recipes.filter(
                Q(title__icontains=search_query) |
                Q(ingredients__icontains=search_query)
            )

        # Apply other filters
        if cuisine_type:
            recipes = recipes.filter(cuisine_type=cuisine_type)
        if language:
            recipes = recipes.filter(language=language)
        if tags:
            for tag in tags:
                recipes = recipes.filter(tags__contains=[tag])
        if difficulty:
            recipes = recipes.filter(difficulty=difficulty)
        if min_rating:
            try:
                min_rating = float(min_rating)
                recipes = recipes.filter(rating__gte=min_rating)
            except ValueError:
                pass

        recipes = recipes.order_by('-created_at')

        # Apply pagination
        paginator = self.pagination_class()
        paginated_recipes = paginator.paginate_queryset(recipes, request)
        serializer = RecipeSerializer(paginated_recipes, many=True)
        
        return paginator.get_paginated_response(serializer.data)

class RecipeDetailView(APIView):
    def get(self, request, recipe_id):
        recipe = get_object_or_404(Recipe, id=recipe_id)
        serializer = RecipeSerializer(recipe)
        return Response(serializer.data)

    def post(self, request, recipe_id):
        """Add rating or update tags for a recipe"""
        recipe = get_object_or_404(Recipe, id=recipe_id)
        
        # Handle rating
        rating = request.data.get('rating')
        if rating is not None:
            try:
                rating = float(rating)
                if not (0 <= rating <= 5):
                    return Response(
                        {'error': 'Rating must be between 0 and 5'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                recipe.update_rating(rating)
            except ValueError:
                return Response(
                    {'error': 'Invalid rating value'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Handle tags
        new_tags = request.data.get('tags')
        if new_tags is not None:
            if not isinstance(new_tags, list):
                return Response(
                    {'error': 'Tags must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            current_tags = set(recipe.tags)
            current_tags.update(new_tags)
            recipe.tags = list(current_tags)
            recipe.save()

        serializer = RecipeSerializer(recipe)
        return Response(serializer.data)

class GenerateRecipeView(APIView):
    def validate_ingredients(self, ingredients):
        if not ingredients or not isinstance(ingredients, list):
            raise ValueError("Les ingrédients doivent être une liste non vide")
        if not all(isinstance(i, str) and i.strip() for i in ingredients):
            raise ValueError("Tous les ingrédients doivent être des chaînes de caractères non vides")
        return [i.strip() for i in ingredients]

    def generate_tags(self, ingredients, cuisine_type, duration):
        """Génère des tags pertinents pour la recette"""
        tags = [cuisine_type.lower()]
        
        if duration <= 15:
            tags.append("rapide")
        elif duration <= 30:
            tags.append("facile")
        elif duration >= 60:
            tags.append("longue-preparation")

        vegetarian_ingredients = {'viande', 'poulet', 'boeuf', 'porc', 'poisson'}
        if not any(ing in ' '.join(ingredients).lower() for ing in vegetarian_ingredients):
            tags.append("vegetarien")
            
        return tags

    def determine_difficulty(self, steps, duration):
        """Détermine la difficulté de la recette"""
        if len(steps) <= 5 and duration <= 30:
            return 'easy'
        elif len(steps) >= 10 or duration >= 90:
            return 'hard'
        return 'medium'

    def generate_recipe(self, ingredients, language, cuisine_type, duration):
        """Génère une recette avec Gemini API"""
        prompt = f"""Tu es un chef cuisinier expert. Génère une recette en {language} qui:
        1. Utilise ces ingrédients principaux: {', '.join(ingredients)}
        2. Est de type cuisine {cuisine_type}
        3. Prend environ {duration} minutes à préparer
        4. Peut ajouter des ingrédients de base courants (sel, poivre, huile, etc.)

        IMPORTANT: La réponse doit être un JSON valide avec cette structure exacte:
        {{
            "title": "Titre de la recette",
            "ingredients": [
                "quantité1 ingrédient1",
                "quantité2 ingrédient2",
                ...
            ],
            "steps": [
                "étape 1 détaillée",
                "étape 2 détaillée",
                ...
            ]
        }}

        Assure-toi que:
        - Le titre est créatif et descriptif
        - Les quantités sont précises et utilisent des unités métriques (g, ml, etc.)
        - Les étapes sont numérotées et détaillées
        - La réponse est strictement en format JSON valide
        """

        start_time = time.time()
        response = model.generate_content(prompt)
        generation_time = time.time() - start_time

        # Extract JSON from the response
        response_text = response.text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        
        recipe_data = json.loads(response_text.strip())
        
        # Validate recipe data
        required_fields = ['title', 'ingredients', 'steps']
        if not all(field in recipe_data for field in required_fields):
            raise ValueError("La recette générée est incomplète")
            
        return recipe_data, generation_time

    def post(self, request):
        try:
            # Extract and validate parameters
            ingredients = self.validate_ingredients(request.data.get('ingredients', []))
            language = request.data.get('language', 'fr').lower()
            cuisine_type = request.data.get('cuisine_type', 'international')
            duration = int(request.data.get('duration', 30))

            if duration < 5 or duration > 240:
                return Response(
                    {'error': 'La durée doit être comprise entre 5 et 240 minutes'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if language not in ['en', 'fr', 'es']:
                return Response(
                    {'error': 'Langue non supportée. Langues disponibles : en, fr, es'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate recipe
            recipe_data, generation_time = self.generate_recipe(
                ingredients, language, cuisine_type, duration
            )

            # Generate tags and determine difficulty
            tags = self.generate_tags(ingredients, cuisine_type, duration)
            difficulty = self.determine_difficulty(recipe_data['steps'], duration)

            # Search for a representative image
            start_time = time.time()
            image_url = search_recipe_image(recipe_data['title'], cuisine_type)
            image_search_time = time.time() - start_time

            # Create recipe object
            recipe = Recipe.objects.create(
                title=recipe_data['title'],
                ingredients=recipe_data['ingredients'],
                steps=recipe_data['steps'],
                cuisine_type=cuisine_type,
                language=language,
                duration=duration,
                tags=tags,
                difficulty=difficulty,
                image_url=image_url
            )
            
            # Prepare response with additional metadata
            serializer = RecipeSerializer(recipe)
            response_data = {
                'recipe': serializer.data,
                'metadata': {
                    'generation_time': round(generation_time, 2),
                    'image_search_time': round(image_search_time, 2),
                    'total_ingredients': len(recipe_data['ingredients']),
                    'total_steps': len(recipe_data['steps']),
                    'is_vegetarian': 'vegetarien' in tags,
                }
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except json.JSONDecodeError as e:
            return Response(
                {'error': "Erreur lors de l'analyse de la réponse de l'IA", 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
