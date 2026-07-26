from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from travel.constants import CATEGORY_KEYS, CATEGORY_LABELS
from travel.media import PROVINCE_COVER, SPOT_IMAGE
from travel.models import (
    Category,
    Destination,
    DestinationCategory,
    Hotel,
    Province,
    TransportMode,
)

from ._seed_data import HOTELS, PROVINCES, TRANSPORT_MODES


class Command(BaseCommand):
    help = "Seed categories, all 7 provinces, and their famous spots."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
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
                    "cover_url": PROVINCE_COVER.get(pdata["slug"], ""),
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
                        "image_url": SPOT_IMAGE.get(
                            spot.get("slug", slugify(spot["name"])), ""
                        ),
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
        # Hotels (demo) — keyed by name within province.
        provinces = {p.slug: p for p in Province.objects.all()}
        n_hotel = 0
        for name, pslug, city, price, star, lat, lng in HOTELS:
            Hotel.objects.update_or_create(
                name=name, province=provinces[pslug],
                defaults={"city": city, "price_npr": price, "star_rating": star,
                          "lat": lat, "lng": lng},
            )
            n_hotel += 1


        n_mode = 0
        for name, emoji, base, per_km, speed, comfort, min_km in TRANSPORT_MODES:
            TransportMode.objects.update_or_create(
                name=name,
                defaults={"emoji": emoji, "base_fare_npr": base, "per_km_npr": per_km,
                          "speed_kmph": speed, "comfort": comfort, "min_km": min_km},
            )
            n_mode += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {n_prov} provinces, "
                f"{n_spot} spots, {n_hotel} hotels, {n_mode} transport modes."
            )
        )
