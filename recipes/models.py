from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Recipe(models.Model):
    title = models.CharField(max_length=200)
    ingredients = models.JSONField()
    steps = models.JSONField()
    cuisine_type = models.CharField(max_length=100)
    language = models.CharField(max_length=10)
    duration = models.IntegerField()  # en minutes
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    ratings_count = models.IntegerField(default=0)
    tags = models.JSONField(default=list)
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ('easy', 'Facile'),
            ('medium', 'Moyen'),
            ('hard', 'Difficile')
        ],
        default='medium'
    )
    image_url = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return self.title

    def update_rating(self, new_rating):
        """Update the average rating when a new rating is added"""
        total_rating = (self.rating * self.ratings_count) + new_rating
        self.ratings_count += 1
        self.rating = total_rating / self.ratings_count
        self.save()
