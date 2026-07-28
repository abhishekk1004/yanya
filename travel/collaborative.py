from __future__ import annotations
from collections import defaultdict
import numpy as np
from .models import Destination, Interaction
from .recommender import Scored, recommend


_EVENT_SCORE = {Interaction.VISITED: 4.5, Interaction.SAVE: 4.0, Interaction.VIEW: 3.0}


def user_item_scores() -> dict[int, dict[int, float]]:
    scores: dict[int, dict[int, float]] = defaultdict(dict)
    rows = Interaction.objects.values("user_id", "destination_id", "event", "rating")
    for it in rows:
        if it["event"] == Interaction.RATE and it["rating"]:
            s = float(it["rating"])
        else:
            s = _EVENT_SCORE.get(it["event"], 0.0)
        if s <= 0:
            continue
        uid, did = it["user_id"], it["destination_id"]
        scores[uid][did] = max(scores[uid].get(did, 0.0), s)
    return scores


def _similar_users(target: dict[int, float], scores, target_uid):
    neighbours = []
    for uid, items in scores.items():
        if uid == target_uid:
            continue
        common = set(target) & set(items)
        if not common:
            continue
        a = np.array([target[i] for i in common])
        b = np.array([items[i] for i in common])
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            continue
        sim = float(a.dot(b) / denom)
        if sim > 0:
            neighbours.append((sim, items))
    return neighbours


def collaborative_recommend(user, top_n: int = 6) -> list[Scored]:

    scores = user_item_scores()
    target = scores.get(user.id, {})
    if not target:
        return []
    neighbours = _similar_users(target, scores, user.id)
    if not neighbours:
        return []

    seen = set(target)
    weighted: dict[int, float] = defaultdict(float)
    simsum: dict[int, float] = defaultdict(float)
    for sim, items in neighbours:
        for did, s in items.items():
            if did in seen:
                continue
            weighted[did] += sim * s
            simsum[did] += sim
    if not weighted:
        return []

    ranked = sorted(
        ((did, weighted[did] / simsum[did]) for did in weighted),
        key=lambda x: x[1], reverse=True,
    )[:top_n]
    ids = [did for did, _ in ranked]
    dests = {
        d.id: d for d in Destination.objects.filter(id__in=ids)
        .select_related("province").prefetch_related("category_weights__category")
    }
    return [Scored(dests[did], round(score, 4)) for did, score in ranked if did in dests]


def hybrid_recommend(user, top_n: int = 6) -> list[Scored]:
    content = recommend(user, top_n=top_n * 2)
    cf = collaborative_recommend(user, top_n=top_n * 2)
    if not cf:
        return content[:top_n]

    def normed(items):
        mx = max((s.score for s in items), default=0.0) or 1.0
        return {s.destination.id: s.score / mx for s in items}

    cmap, fmap = normed(content), normed(cf)
    dests = {s.destination.id: s.destination for s in content + cf}
    blended = {i: 0.6 * cmap.get(i, 0.0) + 0.4 * fmap.get(i, 0.0) for i in dests}
    top = sorted(blended, key=blended.get, reverse=True)[:top_n]
    return [Scored(dests[i], round(blended[i], 4)) for i in top]
