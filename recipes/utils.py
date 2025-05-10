import requests
from django.conf import settings

def search_recipe_image(recipe_title, cuisine_type=None):
    """
    Recherche une image représentative pour une recette via l'API Unsplash.
    Retourne l'URL de l'image trouvée ou None si aucune image n'est trouvée.
    """
    base_url = "https://api.unsplash.com/search/photos"
    # Construit la requête de recherche avec le titre et le type de cuisine
    query = f"food {recipe_title}"
    if cuisine_type and cuisine_type.lower() != "international":
        query += f" {cuisine_type} cuisine"

    params = {
        "query": query,
        "orientation": "landscape",
        "per_page": 1,  # On ne récupère que la meilleure correspondance
        "client_id": settings.UNSPLASH_ACCESS_KEY
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Lève une exception si la requête échoue
        data = response.json()
        
        if data["results"]:
            # Retourne l'URL de la première image trouvée
            return data["results"][0]["urls"]["regular"]
        return None
    
    except Exception as e:
        print(f"Erreur lors de la recherche d'image: {str(e)}")
        return None