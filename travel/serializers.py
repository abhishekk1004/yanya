"""DRF serializers. Kept thin — shaping only, no business logic."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .constants import CATEGORY_KEYS
from .models import (
    Destination,
    Interaction,
    Itinerary,
    ItineraryStop,
    Profile,
    Province,
    UserPreference,
)

User = get_user_model()


# --- Accounts --------------------------------------------------------------
class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def create(self, validated_data: dict) -> "User":
        return User.objects.create_user(**validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("display_name", "bio", "created_at")
        read_only_fields = ("created_at",)


class PreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = (
            "weights",
            "budget_npr",
            "max_difficulty",
            "home_province",
            "quiz_completed",
            "updated_at",
        )
        read_only_fields = ("updated_at",)

    def validate_weights(self, value: dict) -> dict:
        """Coerce weights to the full CATEGORY_KEYS space, clamped to [0, 1]."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("weights must be an object.")
        cleaned: dict[str, float] = {}
        for key in CATEGORY_KEYS:
            try:
                weight = float(value.get(key, 0.0))
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(f"{key} must be numeric.") from exc
            cleaned[key] = min(1.0, max(0.0, weight))
        return cleaned


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    preference = PreferenceSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "profile", "preference")


# --- Catalog ---------------------------------------------------------------
class CategoryWeightSerializer(serializers.Serializer):
    """Flattens a destination's DestinationCategory rows into {key: weight}."""

    def to_representation(self, destination: Destination) -> dict[str, float]:
        return {cw.category.key: cw.weight for cw in destination.category_weights.all()}


class DestinationSerializer(serializers.ModelSerializer):
    province_name = serializers.CharField(source="province.name", read_only=True)
    category_weights = serializers.SerializerMethodField()

    class Meta:
        model = Destination
        fields = (
            "id", "name", "slug", "province", "province_name", "description",
            "lat", "lng", "cost_npr", "difficulty", "best_season", "popularity",
            "is_featured", "category_weights",
        )

    def get_category_weights(self, obj: Destination) -> dict[str, float]:
        # Relies on prefetch_related('category_weights__category') at the view.
        return {cw.category.key: round(cw.weight, 3) for cw in obj.category_weights.all()}


class InteractionSerializer(serializers.ModelSerializer):
    """Write-only-ish: user + destination come from the URL / request."""

    class Meta:
        model = Interaction
        fields = ("event", "rating", "created_at")
        read_only_fields = ("created_at",)

    def validate(self, attrs: dict) -> dict:
        event = attrs.get("event")
        rating = attrs.get("rating")
        if event == Interaction.RATE and not (rating and 1 <= rating <= 5):
            raise serializers.ValidationError("A rate event needs a rating 1–5.")
        if event != Interaction.RATE and rating is not None:
            raise serializers.ValidationError("rating is only valid for rate events.")
        return attrs


class SpotSerializer(serializers.ModelSerializer):
    """Lean destination shape for map markers."""

    class Meta:
        model = Destination
        fields = ("id", "name", "slug", "lat", "lng", "popularity")


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = (
            "id", "name", "slug", "order", "center_lat", "center_lng",
            "boundary_geojson",
        )


class ProvinceWithSpotsSerializer(ProvinceSerializer):
    spots = serializers.SerializerMethodField()

    class Meta(ProvinceSerializer.Meta):
        fields = ProvinceSerializer.Meta.fields + ("spots",)

    def get_spots(self, obj: Province) -> list[dict]:
        # Relies on a prefetched, sliced `famous_spots` attribute set in the view.
        spots = getattr(obj, "famous_spots", obj.destinations.all())
        return SpotSerializer(spots, many=True).data


# --- Itineraries -----------------------------------------------------------
class ItineraryStopSerializer(serializers.ModelSerializer):
    destination = SpotSerializer(read_only=True)

    class Meta:
        model = ItineraryStop
        fields = ("order", "destination", "leg_cost_npr")


class ItinerarySerializer(serializers.ModelSerializer):
    stops = ItineraryStopSerializer(many=True, read_only=True)

    class Meta:
        model = Itinerary
        fields = (
            "id", "name", "budget_npr", "total_cost_npr", "created_at", "stops",
        )
        read_only_fields = ("total_cost_npr", "created_at")
