from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from .constants import CATEGORY_INDEX, CATEGORY_KEYS, NUM_CATEGORIES

CATEGORY_MAP: dict[str, str] = {
    "adventure": "adventure", "wildlife": "adventure", "safari": "adventure",
    "rafting": "adventure", "paragliding": "adventure",
    "historic": "historic", "heritage": "historic", "museum": "historic",
    "palace": "historic", "fort": "historic",
    "religious": "religious", "temple": "religious", "monastery": "religious",
    "pilgrimage": "religious", "spiritual": "religious",
    "hiking": "hiking", "nature": "hiking", "hill station": "hiking",
    "viewpoint": "hiking", "lake": "hiking",
    "trekking": "trekking", "trek": "trekking", "mountaineering": "trekking",
    "base camp": "trekking",
    "popular": "popular", "beach": "popular", "city": "popular", "resort": "popular",
}


@dataclass
class Place:
    place_id: int
    name: str
    vector: np.ndarray  


@dataclass
class Dataset:
    places: dict[int, Place]
    ratings: dict[int, list[tuple[int, float]]] = field(default_factory=dict)


def vector_from_categories(raw: dict[str, float]) -> np.ndarray:
    """Turn a {category_key: weight} dict into a fixed-order 6-vector. O(C)."""
    vec = np.zeros(NUM_CATEGORIES, dtype=float)
    for key, idx in CATEGORY_INDEX.items():
        vec[idx] = float(raw.get(key, 0.0))
    return vec


def load_csv(places_path: str, ratings_path: str) -> Dataset:
    import csv

    places: dict[int, Place] = {}
    with open(places_path, newline="") as fh:
        for row in csv.DictReader(fh):
            pid = int(row["place_id"])
            raw = (row.get("category") or "").strip().lower()
            key = CATEGORY_MAP.get(raw)
            places[pid] = Place(
                pid, row.get("name", f"Place {pid}"),
                vector_from_categories({key: 1.0} if key else {}),
            )

    ratings: dict[int, list[tuple[int, float]]] = {}
    with open(ratings_path, newline="") as fh:
        for row in csv.DictReader(fh):
            uid, pid = int(row["user_id"]), int(row["place_id"])
            if pid in places:
                ratings.setdefault(uid, []).append((pid, float(row["rating"])))
    return Dataset(places=places, ratings=ratings)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def synth_dataset(
    n_places: int = 60, n_users: int = 120, ratings_per_user: int = 15, seed: int = 42
) -> Dataset:

    rng = np.random.default_rng(seed)
    places = {}
    for pid in range(n_places):
      
        vec = np.zeros(NUM_CATEGORIES)
        for idx in rng.choice(NUM_CATEGORIES, size=rng.integers(1, 4), replace=False):
            vec[idx] = rng.uniform(0.4, 1.0)
        places[pid] = Place(pid, f"Place {pid}", vec)

    ratings: dict[int, list[tuple[int, float]]] = {}
    place_ids = list(places)
    for uid in range(n_users):
        taste = np.zeros(NUM_CATEGORIES)
        for idx in rng.choice(NUM_CATEGORIES, size=rng.integers(1, 3), replace=False):
            taste[idx] = rng.uniform(0.5, 1.0)
        chosen = rng.choice(place_ids, size=ratings_per_user, replace=False)
        user_ratings = []
        for pid in chosen:
            sim = _cosine(taste, places[pid].vector)
            rating = float(np.clip(round(1 + 4 * sim + rng.normal(0, 0.5)), 1, 5))
            user_ratings.append((int(pid), rating))
        ratings[uid] = user_ratings
    return Dataset(places=places, ratings=ratings)


def _split(user_ratings: list[tuple[int, float]], rng, test_frac=0.2):

    idx = np.arange(len(user_ratings))
    rng.shuffle(idx)
    n_test = max(1, int(len(idx) * test_frac))
    test_i = set(idx[:n_test].tolist())
    train = [r for i, r in enumerate(user_ratings) if i not in test_i]
    test = [r for i, r in enumerate(user_ratings) if i in test_i]
    return train, test


def _taste_from_train(train, places: dict[int, Place]) -> np.ndarray:
    acc = np.zeros(NUM_CATEGORIES)
    total = 0.0
    for pid, rating in train:
        acc += rating * places[pid].vector
        total += rating
    return acc / total if total else acc


@dataclass
class Metrics:
    rmse: float
    mae: float
    baseline_rmse: float
    baseline_mae: float
    recall_at_k: float
    random_recall_at_k: float
    k: int
    n_users: int
    n_train: int = 0   
    n_test: int = 0    

def _predict(place_vec, train, places, user_mean):

    num = den = 0.0
    for pid, rating in train:
        sim = max(0.0, _cosine(place_vec, places[pid].vector))
        if sim > 0:
            num += sim * rating
            den += sim
    return num / den if den else user_mean


def evaluate(data: Dataset, k: int = 5, seed: int = 0) -> Metrics:
    rng = np.random.default_rng(seed)
    global_mean = float(
        np.mean([r for rs in data.ratings.values() for _, r in rs]) or 3.0
    )

    sq_err, abs_err, base_sq, base_abs, n_pred = 0.0, 0.0, 0.0, 0.0, 0
    recalls, rand_recalls = [], []
    n_train_total, n_test_total = 0, 0
    place_ids = list(data.places)

    for uid, user_ratings in data.ratings.items():
        if len(user_ratings) < 2:
            continue
        train, test = _split(user_ratings, rng)
        n_train_total += len(train)
        n_test_total += len(test)
        user_mean = float(np.mean([r for _, r in train])) if train else global_mean

        
        for pid, actual in test:
            pred = _predict(data.places[pid].vector, train, data.places, user_mean)
            sq_err += (pred - actual) ** 2
            abs_err += abs(pred - actual)
            base_sq += (global_mean - actual) ** 2
            base_abs += abs(global_mean - actual)
            n_pred += 1
        liked = {pid for pid, r in test if r >= 4}
        if liked:
            trained_ids = {pid for pid, _ in train}
            candidates = [p for p in place_ids if p not in trained_ids]
            scored = sorted(
                candidates,
                key=lambda p: _predict(data.places[p].vector, train, data.places, user_mean),
                reverse=True,
            )
            top_k = set(scored[:k])
            recalls.append(len(top_k & liked) / len(liked))
            rand = set(rng.choice(candidates, size=min(k, len(candidates)),
                                  replace=False).tolist())
            rand_recalls.append(len(rand & liked) / len(liked))

    return Metrics(
        rmse=(sq_err / n_pred) ** 0.5 if n_pred else 0.0,
        mae=abs_err / n_pred if n_pred else 0.0,
        baseline_rmse=(base_sq / n_pred) ** 0.5 if n_pred else 0.0,
        baseline_mae=base_abs / n_pred if n_pred else 0.0,
        recall_at_k=float(np.mean(recalls)) if recalls else 0.0,
        random_recall_at_k=float(np.mean(rand_recalls)) if rand_recalls else 0.0,
        k=k,
        n_users=len(data.ratings),
        n_train=n_train_total,
        n_test=n_test_total,
    )
