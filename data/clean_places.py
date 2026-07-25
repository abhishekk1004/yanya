
import csv
import json
import math
import os
import re

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "nepal_places_raw.json")
OUT = os.path.join(HERE, "nepal_places_clean.csv")

PROVINCES = [
    ("Koshi", 27.30, 87.30), ("Madhesh", 26.80, 85.90), ("Bagmati", 27.70, 85.40),
    ("Gandaki", 28.40, 84.00), ("Lumbini", 27.60, 82.80), ("Karnali", 29.30, 82.20),
    ("Sudurpashchim", 29.30, 80.90),
]


KIND_COST = {
    "temple": 100, "monastery": 200, "monument": 150, "museum": 300,
    "national_park": 1500, "peak": 0, "lake": 100, "waterfall": 100,
    "viewpoint": 0, "attraction": 200,
}

KIND_CATEGORY = {
    "temple": "religious", "monastery": "religious", "monument": "historic",
    "museum": "historic", "national_park": "adventure", "peak": "trekking",
    "lake": "hiking", "waterfall": "hiking", "viewpoint": "hiking",
    "attraction": "popular",
}


def haversine(a_lat, a_lng, b_lat, b_lng):
    r = 6371.0
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(dlmb / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def nearest_province(lat, lng):
    return min(PROVINCES, key=lambda p: haversine(lat, lng, p[1], p[2]))[0]


def classify(tags):
    """Map raw OSM tags → (kind, category). O(1)."""
    name = (tags.get("name") or "").lower()
    hist = tags.get("historic", "")
    if tags.get("waterway") == "waterfall":
        return "waterfall", KIND_CATEGORY["waterfall"]
    if tags.get("natural") == "peak":
        return "peak", KIND_CATEGORY["peak"]
    if tags.get("natural") == "water" or "lake" in name or "tal" in name.split():
        return "lake", KIND_CATEGORY["lake"]
    if tags.get("boundary") == "national_park":
        return "national_park", KIND_CATEGORY["national_park"]
    if tags.get("tourism") == "museum":
        return "museum", KIND_CATEGORY["museum"]
    if tags.get("tourism") == "viewpoint":
        return "viewpoint", KIND_CATEGORY["viewpoint"]
    if hist in ("temple", "shrine") or any(
        w in name for w in ("temple", "mandir", "stupa", "gumba", "math")
    ):
        return "temple", KIND_CATEGORY["temple"]
    if hist == "monastery" or "monastery" in name or "gompa" in name:
        return "monastery", KIND_CATEGORY["monastery"]
    if hist in ("monument", "memorial", "archaeological_site", "ruins", "castle"):
        return "monument", KIND_CATEGORY["monument"]
    return "attraction", KIND_CATEGORY["attraction"]




BLOCK = re.compile(
    r"\b(pvt|p\.?\s?ltd|ltd|consultancy|engineering|suppliers?|traders?|"
    r"enterprises?|store|mart|shop|clinic|hospital|pharmacy|bank|school|"
    r"college|campus|institute|academy|office|hotel|lodge|guest\s?house|"
    r"restaurant|cafe|cafeteria|bar|salon|workshop|garage|motors?|furniture|"
    r"tailors?|studio|tower|apartment|petrol|filling\s?station|chowk|marga|road)\b",
    re.IGNORECASE,
)


def coords(el):
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    return (c["lat"], c["lon"]) if c else (None, None)


def main():
    data = json.load(open(RAW))
    seen = set()
    rows = []
    dropped_noname = dropped_dup = dropped_nocoord = 0
    NEPAL = (26.3, 30.5, 80.0, 88.3)  

    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = (tags.get("name") or "").strip()
        if not name or not re.search(r"[A-Za-zऀ-ॿ]", name) or BLOCK.search(name):
            dropped_noname += 1
            continue
        lat, lng = coords(el)
        if lat is None or not (NEPAL[0] <= lat <= NEPAL[1] and NEPAL[2] <= lng <= NEPAL[3]):
            dropped_nocoord += 1
            continue
        key = (name.lower(), round(lat, 3), round(lng, 3))
        if key in seen:
            dropped_dup += 1
            continue
        seen.add(key)
        kind, category = classify(tags)
        rows.append({
            "place_id": el.get("id"),
            "name": name,
            "province": nearest_province(lat, lng),
            "category": category,
            "kind": kind,
            "cost_npr": KIND_COST.get(kind, 200),
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "elevation_m": tags.get("ele", ""),
        })

    rows.sort(key=lambda r: (r["province"], r["category"], r["name"]))
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"raw elements     : {len(data.get('elements', []))}")
    print(f"dropped no-name  : {dropped_noname}")
    print(f"dropped no-coord : {dropped_nocoord}")
    print(f"dropped duplicate: {dropped_dup}")
    print(f"clean rows       : {len(rows)}  -> {OUT}")
    from collections import Counter
    print("by category      :", dict(Counter(r["category"] for r in rows)))


if __name__ == "__main__":
    main()
