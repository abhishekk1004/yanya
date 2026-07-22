"""Seed the 6 categories, 7 provinces and their famous spots.

Idempotent: re-running updates existing rows (keyed by slug/key) and never
duplicates. Popularity is left at 0 here; the nightly Celery task computes it
from interactions. Run: ``python manage.py seed_provinces``.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from travel.constants import CATEGORY_KEYS, CATEGORY_LABELS
from travel.models import Category, Destination, DestinationCategory, Province

from ._seed_data import PROVINCES


class Command(BaseCommand):
    help = "Seed categories, all 7 provinces, and their famous spots."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        # Time/space: O(spots × categories) — a few dozen rows; trivial.
        categories = {
            key: Category.objects.update_or_create(
                key=key, defaults={"label": CATEGORY_LABELS[key]}
            )[0]
            for key in CATEGORY_KEYS
        }
        n_prov = n_spot = 0
        for pdata in PROVINCES:
            province, _ = Province.objects.update_or_create(
                slug=pdata["slug"],
                defaults={
                    "name": pdata["name"],
                    "order": pdata["order"],
                    "center_lat": pdata["center_lat"],
                    "center_lng": pdata["center_lng"],
                },
            )
            n_prov += 1
            for spot in pdata["spots"]:
                dest, _ = Destination.objects.update_or_create(
                    slug=spot.get("slug", slugify(spot["name"])),
                    defaults={
                        "name": spot["name"],
                        "province": province,
                        "lat": spot["lat"],
                        "lng": spot["lng"],
                        "cost_npr": spot["cost_npr"],
                        "difficulty": spot["difficulty"],
                        "best_season": spot["best_season"],
                        "is_featured": True,
                        # Baseline popularity from the "popular" axis so the
                        # /popular list is meaningful before any interactions.
                        # The nightly task overwrites this with a blended score.
                        "popularity": round(spot["w"].get("popular", 0.0) * 100, 1),
                    },
                )
                n_spot += 1
                for key, weight in spot["w"].items():
                    DestinationCategory.objects.update_or_create(
                        destination=dest,
                        category=categories[key],
                        defaults={"weight": weight},
                    )
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {n_prov} provinces, "
                f"{n_spot} spots."
            )
        )
