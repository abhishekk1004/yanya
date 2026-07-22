from __future__ import annotations

import math

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from .models import Destination, Interaction
from .recommender import rebuild_behavioural_for_user


@shared_task
def refresh_popularity() -> int:
    counts = {
        row["id"]: row
        for row in Destination.objects.values("id").annotate(
            views=Count("interactions", filter=Q(interactions__event=Interaction.VIEW)),
            saves=Count("interactions", filter=Q(interactions__event=Interaction.SAVE)),
            visits=Count("interactions", filter=Q(interactions__event=Interaction.VISITED)),
        )
    }
    dests = list(
        Destination.objects.prefetch_related("category_weights__category")
    )
    raw_signal: dict[int, float] = {}
    for d in dests:
        c = counts.get(d.id, {})
        signal = 0.3 * c.get("views", 0) + 1.0 * c.get("saves", 0) + 1.5 * c.get("visits", 0)
        raw_signal[d.id] = math.log1p(signal)
    max_signal = max(raw_signal.values(), default=0.0) or 1.0

    for d in dests:
        popular_weight = next(
            (cw.weight for cw in d.category_weights.all() if cw.category.key == "popular"),
            0.0,
        )
        interaction_component = raw_signal[d.id] / max_signal  # 0–1
        d.popularity = round(50.0 * popular_weight + 50.0 * interaction_component, 1)
    Destination.objects.bulk_update(dests, ["popularity"])
    return len(dests)


@shared_task
def rebuild_behavioural_taste() -> int:
    User = get_user_model()
    users = User.objects.filter(interactions__isnull=False).distinct()
    n = 0
    for user in users:
        rebuild_behavioural_for_user(user)
        n += 1
    return n
