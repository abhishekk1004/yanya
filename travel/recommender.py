"""Content-based recommender.

Design (deliberately lean — no user×destination matrix):
  * Each destination is a vector over the six CATEGORY_KEYS (its weighted
    DestinationCategory rows).
  * A user's taste is a single 6-vector: their explicit quiz weights blended
    with a behavioural vector (the rating-weighted average of destinations they
    liked). Behaviour is weighted more as interactions accumulate, so a
    brand-new user falls back cleanly to their quiz weights (cold start).
  * Candidates are scored by cosine similarity to the taste vector, after hard
    filters (budget / difficulty / season / province) and hiding visited places.

Complexity: building the taste vector is O(interactions × C); scoring is one
matrix–vector product, O(D × C), where C = 6 categories. No dense N×M matrix.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import CATEGORY_INDEX, NUM_CATEGORIES
from .models import Destination, Interaction, UserPreference

# Implicit "liking" strength per event type, used to weight behavioural taste.
EVENT_SIGNAL = {
    Interaction.SAVE: 3.0,
    Interaction.VISITED: 4.0,
    Interaction.VIEW: 0.5,
}
BLEND_K = 8.0  # behaviour reaches half-weight after this many signalled events


@dataclass
class Scored:
    destination: Destination
    score: float


def category_vector(dest: Destination) -> np.ndarray:
    """The destination's feature vector over CATEGORY_KEYS. O(C)."""
    vec = np.zeros(NUM_CATEGORIES, dtype=float)
    for cw in dest.category_weights.all():
        idx = CATEGORY_INDEX.get(cw.category.key)
        if idx is not None:
            vec[idx] = cw.weight
    return vec


def destinations_with_vectors(queryset) -> tuple[list[Destination], np.ndarray]:
    """Materialise a candidate queryset into (destinations, D×C matrix). O(D×C)."""
    dests = list(queryset.prefetch_related("category_weights__category"))
    if not dests:
        return [], np.zeros((0, NUM_CATEGORIES))
    matrix = np.vstack([category_vector(d) for d in dests])
    return dests, matrix


def explicit_taste(pref: UserPreference) -> np.ndarray:
    """The quiz weights as a fixed-order 6-vector. O(C)."""
    vec = np.zeros(NUM_CATEGORIES, dtype=float)
    for key, idx in CATEGORY_INDEX.items():
        vec[idx] = float(pref.weights.get(key, 0.0))
    return vec


def behavioural_taste(user) -> tuple[np.ndarray, int]:
    """Rating-weighted average of the vectors of destinations the user liked.

    Returns (vector, n_signals). RATE events are weighted by their rating;
    SAVE/VISITED/VIEW by a fixed implicit signal. O(interactions × C).
    """
    interactions = (
        Interaction.objects.filter(user=user)
        .select_related("destination")
        .prefetch_related("destination__category_weights__category")
    )
    acc = np.zeros(NUM_CATEGORIES, dtype=float)
    total_weight = 0.0
    n_signals = 0
    for it in interactions:
        if it.event == Interaction.RATE and it.rating:
            weight = float(it.rating)  # 1–5: higher rating pulls harder
        else:
            weight = EVENT_SIGNAL.get(it.event, 0.0)
        if weight <= 0:
            continue
        acc += weight * category_vector(it.destination)
        total_weight += weight
        n_signals += 1
    if total_weight == 0:
        return np.zeros(NUM_CATEGORIES), 0
    return acc / total_weight, n_signals


def blended_taste(user) -> np.ndarray:
    """Blend explicit + behavioural taste, weighting behaviour more with data.

    alpha = n / (n + K): 0 at cold start (pure quiz weights), → 1 as the user
    interacts. O(interactions × C).
    """
    pref, _ = UserPreference.objects.get_or_create(user=user)
    explicit = explicit_taste(pref)
    behaviour, n = behavioural_taste(user)
    alpha = n / (n + BLEND_K) if n else 0.0
    return (1.0 - alpha) * explicit + alpha * behaviour


def _cosine(matrix: np.ndarray, taste: np.ndarray) -> np.ndarray:
    """Cosine similarity of each row of `matrix` with `taste`. O(D×C)."""
    taste_norm = np.linalg.norm(taste)
    if taste_norm == 0:
        return np.zeros(matrix.shape[0])
    row_norms = np.linalg.norm(matrix, axis=1)
    row_norms[row_norms == 0] = 1e-9
    return (matrix @ taste) / (row_norms * taste_norm)


def candidate_queryset(user, province: str | None = None, season: str | None = None):
    """Apply hard filters and hide already-visited places. O(D) in SQL."""
    pref, _ = UserPreference.objects.get_or_create(user=user)
    qs = Destination.objects.select_related("province")
    qs = qs.filter(cost_npr__lte=pref.budget_npr)
    qs = qs.filter(difficulty__lte=pref.max_difficulty)
    if season:
        qs = qs.filter(best_season__in=[season, "all"])
    if province:
        if str(province).isdigit():
            qs = qs.filter(province_id=int(province))
        else:
            qs = qs.filter(province__slug=province)
    visited = Interaction.objects.filter(
        user=user, event=Interaction.VISITED
    ).values_list("destination_id", flat=True)
    return qs.exclude(id__in=list(visited))


def recommend(
    user, province: str | None = None, top_n: int = 10, season: str | None = None
) -> list[Scored]:
    """Top-N content-based recommendations for `user`.

    Falls back to popularity ordering when the taste vector is all-zero (a user
    who neither took the quiz nor interacted). O(interactions × C + D×C).
    """
    dests, matrix = destinations_with_vectors(
        candidate_queryset(user, province=province, season=season)
    )
    if not dests:
        return []
    taste = blended_taste(user)
    if np.linalg.norm(taste) == 0:
        ranked = sorted(dests, key=lambda d: d.popularity, reverse=True)
        return [Scored(d, d.popularity) for d in ranked[:top_n]]
    scores = _cosine(matrix, taste)
    order = np.argsort(-scores)[:top_n]
    return [Scored(dests[i], float(scores[i])) for i in order]


def rebuild_behavioural_for_user(user) -> None:
    """Persist a user's behavioural taste onto their preference (nightly job)."""
    vec, n = behavioural_taste(user)
    pref, _ = UserPreference.objects.get_or_create(user=user)
    pref.behavioural_weights = {
        k: round(float(vec[i]), 4) for k, i in CATEGORY_INDEX.items()
    }
    pref.interaction_count = n
    pref.save(update_fields=["behavioural_weights", "interaction_count", "updated_at"])
