import json

from django.core.management.base import BaseCommand, CommandError

from travel.models import Province


def _round_ring(ring, precision, keep):
    out = []
    for i, (x, y) in enumerate(ring):
        if i % keep == 0 or i == len(ring) - 1:
            out.append([round(x, precision), round(y, precision)])
    if len(out) < 4: 
        out = [[round(x, precision), round(y, precision)] for x, y in ring[:4]]
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def _simplify(geometry, precision, keep):

    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Polygon":
        geometry["coordinates"] = [_round_ring(r, precision, keep) for r in coords]
    elif gtype == "MultiPolygon":
        geometry["coordinates"] = [
            [_round_ring(r, precision, keep) for r in poly] for poly in coords
        ]
    return geometry


class Command(BaseCommand):
    help = "Load + simplify province boundary polygons from a GeoJSON file."

    def add_arguments(self, parser) -> None:
        parser.add_argument("geojson")
        parser.add_argument("--name-prop", default="name")
        parser.add_argument("--order-prop", default="",
                            help="property holding the province number (1..7)")
        parser.add_argument("--precision", type=int, default=3)
        parser.add_argument("--keep", type=int, default=4,
                            help="keep every Nth boundary point")

    def handle(self, *args, **opts) -> None:
        try:
            with open(opts["geojson"]) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read GeoJSON: {exc}") from exc

        by_name = {p.name.lower(): p for p in Province.objects.all()}
        by_order = {p.order: p for p in Province.objects.all()}
        matched = 0
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            province = None
            if opts["order_prop"] and props.get(opts["order_prop"]) is not None:
                try:
                    province = by_order.get(int(str(props[opts["order_prop"]]).strip()))
                except ValueError:
                    province = None
            if province is None:
                name = str(props.get(opts["name_prop"], "")).lower()
                province = by_name.get(name) or next(
                    (p for k, p in by_name.items() if k in name or name in k), None
                )
            if not province:
                continue
            geom = _simplify(feature.get("geometry", {}), opts["precision"], opts["keep"])
            province.boundary_geojson = geom
            province.save(update_fields=["boundary_geojson"])
            matched += 1

        self.stdout.write(self.style.SUCCESS(
            f"Loaded + simplified boundaries for {matched}/{len(by_order)} provinces."
        ))
