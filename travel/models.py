"""Data model for the Nepal travel app.

The load-bearing piece is DestinationCategory.weight: each destination is a
weighted vector over the six CATEGORY_KEYS, and that vector is exactly what the
content-based recommender scores against a user's taste vector.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import CATEGORY_KEYS

DIFFICULTY_CHOICES = [
    (1, "Very easy"),
    (2, "Easy"),
    (3, "Moderate"),
    (4, "Hard"),
    (5, "Very hard"),
]

SEASON_CHOICES = [
    ("all", "All year"),
    ("spring", "Spring"),
    ("summer", "Summer"),
    ("autumn", "Autumn"),
    ("winter", "Winter"),
]


# --- Accounts --------------------------------------------------------------
class User(AbstractUser):
    """Custom user set from the start so later changes avoid painful swaps."""

    email = models.EmailField("email address", unique=True)

    def __str__(self) -> str:
        return self.get_username()


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Profile<{self.user}>"


def default_weights() -> dict[str, float]:
    """Neutral taste: all categories zero until the quiz sets them."""
    return {key: 0.0 for key in CATEGORY_KEYS}


class UserPreference(models.Model):
    """Explicit taste vector + hard filters the recommender applies.

    ``weights`` is a dict keyed by CATEGORY_KEYS with values in [0, 1]; for a
    brand-new user these ticked quiz interests *are* their taste (cold start).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preference"
    )
    weights = models.JSONField(default=default_weights)
    # Behavioural taste rebuilt nightly from interactions (dict over
    # CATEGORY_KEYS). Blended with `weights`, weighted more as interactions grow.
    behavioural_weights = models.JSONField(default=dict, blank=True)
    interaction_count = models.PositiveIntegerField(default=0)
    budget_npr = models.PositiveIntegerField(default=50000)
    max_difficulty = models.PositiveSmallIntegerField(
        choices=DIFFICULTY_CHOICES, default=5
    )
    home_province = models.ForeignKey(
        "travel.Province",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="residents",
    )
    quiz_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Preference<{self.user}>"


# --- Catalog ---------------------------------------------------------------
class Province(models.Model):
    """One of Nepal's 7 provinces."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    order = models.PositiveSmallIntegerField(default=0)  # west→east cycle order
    # Centroid for map framing; GeoJSON boundary added in Phase 5.
    center_lat = models.FloatField(default=28.0)
    center_lng = models.FloatField(default=84.0)
    boundary_geojson = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    """A category axis. ``key`` is one of CATEGORY_KEYS."""

    key = models.CharField(max_length=20, unique=True)
    label = models.CharField(max_length=40)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.label


class Destination(models.Model):
    """A place to visit, living in exactly one province."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="destinations"
    )
    description = models.TextField(blank=True)
    lat = models.FloatField()
    lng = models.FloatField()
    # Hard-filter attributes.
    cost_npr = models.PositiveIntegerField(default=0)  # typical visit cost
    difficulty = models.PositiveSmallIntegerField(
        choices=DIFFICULTY_CHOICES, default=1
    )
    best_season = models.CharField(
        max_length=10, choices=SEASON_CHOICES, default="all"
    )
    # Popularity score, refreshed nightly by Celery.
    popularity = models.FloatField(default=0.0)
    categories = models.ManyToManyField(
        Category, through="DestinationCategory", related_name="destinations"
    )
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-popularity", "name"]
        indexes = [models.Index(fields=["province", "difficulty"])]

    def __str__(self) -> str:
        return self.name


class DestinationCategory(models.Model):
    """Through row: the weight of one category for one destination, in [0, 1].

    Collectively these rows are the destination's feature vector.
    """

    destination = models.ForeignKey(
        Destination, on_delete=models.CASCADE, related_name="category_weights"
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    weight = models.FloatField(default=0.0)

    class Meta:
        unique_together = ("destination", "category")

    def __str__(self) -> str:
        return f"{self.destination}·{self.category}={self.weight:.2f}"


# --- Behaviour -------------------------------------------------------------
class Interaction(models.Model):
    """A logged user↔destination event feeding behavioural taste + popularity."""

    VIEW = "view"
    SAVE = "save"
    RATE = "rate"
    VISITED = "visited"
    EVENT_CHOICES = [
        (VIEW, "Viewed"),
        (SAVE, "Saved"),
        (RATE, "Rated"),
        (VISITED, "Visited"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interactions"
    )
    destination = models.ForeignKey(
        Destination, on_delete=models.CASCADE, related_name="interactions"
    )
    event = models.CharField(max_length=10, choices=EVENT_CHOICES)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–5 if RATE
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "destination"]),
            models.Index(fields=["destination", "event"]),
        ]

    def __str__(self) -> str:
        return f"{self.user}·{self.event}·{self.destination}"


# --- Itineraries -----------------------------------------------------------
class Itinerary(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="itineraries"
    )
    name = models.CharField(max_length=120, default="My trip")
    budget_npr = models.PositiveIntegerField(default=50000)
    total_cost_npr = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"


class ItineraryStop(models.Model):
    """An ordered stop on an itinerary. ``order`` is the optimised visit order."""

    itinerary = models.ForeignKey(
        Itinerary, on_delete=models.CASCADE, related_name="stops"
    )
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)
    leg_cost_npr = models.PositiveIntegerField(default=0)  # travel cost to reach

    class Meta:
        ordering = ["order"]
        unique_together = ("itinerary", "destination")

    def __str__(self) -> str:
        return f"{self.itinerary.name}#{self.order}:{self.destination}"
