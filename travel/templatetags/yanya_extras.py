"""Small template helpers for Yanya."""
from django import template

from travel.media import CATEGORY_GRADIENT, gradient_for

register = template.Library()


@register.filter
def card_gradient(destination) -> str:
    """CSS gradient for a destination card, from its category keys (or default)."""
    try:
        keys = [cw.category.key for cw in destination.category_weights.all()]
    except Exception:
        keys = []
    return gradient_for(keys)


@register.filter
def top_tags(destination, limit: int = 3):
    """Up to `limit` category labels with the highest weight (for card tags)."""
    try:
        rows = sorted(
            destination.category_weights.all(), key=lambda cw: cw.weight, reverse=True
        )
    except Exception:
        rows = []
    return [cw.category.label for cw in rows[:limit]]
