"""Write a synthetic tourism dataset (places.csv + ratings.csv) sharing the same
schema as a real Kaggle tourism dataset, so the eval pipeline runs with no
network. Each place gets a single free-text ``category`` (Kaggle-style) that the
loader maps onto the six category keys.

    python manage.py generate_synthetic --out data/
"""
import csv
import os

import numpy as np
from django.core.management.base import BaseCommand

from travel.constants import CATEGORY_KEYS

# One representative Kaggle-style category label per key (round-trips via
# evaluation.CATEGORY_MAP).
RAW_LABEL = {
    "adventure": "adventure", "historic": "heritage", "religious": "temple",
    "hiking": "hill station", "trekking": "trek", "popular": "city",
}
PROVINCES = ["Koshi", "Madhesh", "Bagmati", "Gandaki", "Lumbini", "Karnali",
             "Sudurpashchim"]
SEASONS = ["all", "spring", "summer", "autumn", "winter"]


class Command(BaseCommand):
    help = "Generate a Kaggle-schema synthetic dataset (places.csv, ratings.csv)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--out", default="data", help="output directory")
        parser.add_argument("--places", type=int, default=60)
        parser.add_argument("--users", type=int, default=120)
        parser.add_argument("--ratings-per-user", type=int, default=15)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts) -> None:
        rng = np.random.default_rng(opts["seed"])
        os.makedirs(opts["out"], exist_ok=True)
        n_places, n_users = opts["places"], opts["users"]

        # Each place has one dominant category (like a Kaggle "Type" column).
        place_cat = {}
        places_path = os.path.join(opts["out"], "places.csv")
        with open(places_path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["place_id", "name", "province", "category", "cost_npr",
                        "difficulty", "best_season", "lat", "lng"])
            for pid in range(n_places):
                key = CATEGORY_KEYS[int(rng.integers(0, len(CATEGORY_KEYS)))]
                place_cat[pid] = key
                w.writerow([
                    pid, f"Place {pid}", PROVINCES[pid % 7], RAW_LABEL[key],
                    int(rng.integers(2, 120) * 1000), int(rng.integers(1, 6)),
                    SEASONS[int(rng.integers(0, len(SEASONS)))],
                    round(26 + rng.random() * 4, 4), round(80 + rng.random() * 8, 4),
                ])

        # Users prefer 1–2 categories; rate places, higher when category matches.
        ratings_path = os.path.join(opts["out"], "ratings.csv")
        with open(ratings_path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["user_id", "place_id", "rating"])
            for uid in range(n_users):
                liked = set(rng.choice(len(CATEGORY_KEYS),
                                       size=int(rng.integers(1, 3)), replace=False))
                liked_keys = {CATEGORY_KEYS[i] for i in liked}
                chosen = rng.choice(n_places, size=opts["ratings_per_user"],
                                    replace=False)
                for pid in chosen:
                    base = 4.2 if place_cat[int(pid)] in liked_keys else 2.0
                    rating = int(np.clip(round(base + rng.normal(0, 0.6)), 1, 5))
                    w.writerow([uid, int(pid), rating])

        self.stdout.write(self.style.SUCCESS(
            f"Wrote {places_path} and {ratings_path} "
            f"({n_places} places, {n_users} users)."
        ))
