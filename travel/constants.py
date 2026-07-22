
CATEGORY_KEYS: tuple[str, ...] = (
    "adventure",
    "historic",
    "religious",
    "hiking",
    "trekking",
    "popular",
)

CATEGORY_LABELS: dict[str, str] = {
    "adventure": "Adventure",
    "historic": "Historic",
    "religious": "Religious",
    "hiking": "Hiking",
    "trekking": "Trekking",
    "popular": "Popular",
}

CATEGORY_INDEX: dict[str, int] = {key: i for i, key in enumerate(CATEGORY_KEYS)}
NUM_CATEGORIES: int = len(CATEGORY_KEYS)

PROVINCE_NAMES: tuple[str, ...] = (
    "Koshi",
    "Madhesh",
    "Bagmati",
    "Gandaki",
    "Lumbini",
    "Karnali",
    "Sudurpashchim",
)
