"""Load real province boundaries from a GeoJSON FeatureCollection.

Matches each feature to a Province by a name property (case-insensitive,
configurable) and stores the geometry on ``Province.boundary_geojson``; the home
map then draws real outlines instead of centroid circles. With no file the map
falls back to circles, so this is optional polish.

    python manage.py load_boundaries data/nepal_provinces.geojson --name-prop NAME

The bundled data/README explains where to fetch an open Nepal provinces GeoJSON.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from travel.models import Province


class Command(BaseCommand):
    help = "Load province boundary polygons from a GeoJSON file."

    def add_arguments(self, parser) -> None:
        parser.add_argument("geojson", help="path to a GeoJSON FeatureCollection")
        parser.add_argument(
            "--name-prop", default="name",
            help="feature property holding the province name (default: name)",
        )

    def handle(self, *args, **opts) -> None:
        try:
            with open(opts["geojson"]) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read GeoJSON: {exc}") from exc

        by_name = {p.name.lower(): p for p in Province.objects.all()}
        matched = 0
        for feature in data.get("features", []):
            name = str(feature.get("properties", {}).get(opts["name_prop"], "")).lower()
            # Tolerate "Province 3", "Bagmati Province" style variants.
            province = by_name.get(name) or next(
                (p for key, p in by_name.items() if key in name or name in key), None
            )
            if not province:
                continue
            province.boundary_geojson = feature.get("geometry")
            province.save(update_fields=["boundary_geojson"])
            matched += 1

        self.stdout.write(self.style.SUCCESS(
            f"Loaded boundaries for {matched}/{len(by_name)} provinces."
        ))
