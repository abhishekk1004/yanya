from __future__ import annotations


def wm(filename: str, width: int = 1000) -> str:
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width={width}"



CATEGORY_GRADIENT: dict[str, str] = {
    "adventure": "linear-gradient(135deg,#0b3d2e,#12775a)",
    "historic": "linear-gradient(135deg,#3a2a12,#8a5a1e)",
    "religious": "linear-gradient(135deg,#3a0d1e,#a3123c)",
    "hiking": "linear-gradient(135deg,#12324f,#2f7fb5)",
    "trekking": "linear-gradient(135deg,#0d2036,#1e5bd6)",
    "popular": "linear-gradient(135deg,#3a1046,#b0308f)",
    "_default": "linear-gradient(135deg,#101a3a,#1e5bd6)",
}


GALLERY: list[dict[str, str]] = [
    {"title": "The Himalaya", "url": wm("Mount_Everest_as_seen_from_Drukair2_PLW_edit.jpg")},
    {"title": "Ama Dablam", "url": wm("Ama_Dablam.jpg")},
    {"title": "Janaki temple", "url": wm("Janaki_Mandir.jpg")},
    {"title": "Lumbini, birthplace of Buddha", "url": wm("Mayadevi_Temple,_Lumbini.jpg")},
    {"title": "Boudhanath stupa", "url": wm("Boudhanath.jpg")},
    {"title": "Phewa lake, Pokhara", "url": wm("Phewa_Lake_Pokhara.jpg")},
    {"title": "Rara lake", "url": wm("Rara_Lake_Nepal.jpg")},
    {"title": "Danphe, the national bird", "url": wm("Lophophorus_impejanus_-_Himalayan_Monal.jpg")},
    {"title": "One-horned rhino", "url": wm("Indian_Rhinoceros.jpg")},
]


SPOT_IMAGE: dict[str, str] = {
    "everest-base-camp": wm("Mount_Everest_as_seen_from_Drukair2_PLW_edit.jpg"),
    "kanchenjunga-base-camp": wm("Kangchenjunga_India.jpg"),
    "pathibhara-temple": wm("Pathibhara_Temple.jpg"),
    "ilam-tea-gardens": wm("Ilam_Tea_Garden.jpg"),
    "janaki-temple": wm("Janaki_Mandir.jpg"),
    "gadhimai-temple": wm("Gadhimai.jpg"),
    "parsa-national-park": wm("Parsa_Wildlife_Reserve.jpg"),
    "pashupatinath-temple": wm("Pashupatinath_Temple.jpg"),
    "boudhanath-stupa": wm("Boudhanath.jpg"),
    "kathmandu-durbar-square": wm("Kathmandu_Durbar_Square.jpg"),
    "chitwan-national-park": wm("Indian_Rhinoceros.jpg"),
    "nagarkot": wm("Nagarkot_Sunrise.jpg"),
    "phewa-lake-pokhara": wm("Phewa_Lake_Pokhara.jpg"),
    "annapurna-base-camp": wm("Annapurna_Base_Camp.jpg"),
    "muktinath-temple": wm("Muktinath_Temple.jpg"),
    "poon-hill-ghorepani": wm("Poon_Hill.jpg"),
    "sarangkot": wm("Sarangkot,_Pokhara.jpg"),
    "lumbini-buddha": wm("Mayadevi_Temple,_Lumbini.jpg"),
    "tansen-palpa": wm("Tansen_Palpa.jpg"),
    "bardia-national-park": wm("Bengal_Tiger.jpg"),
    "swargadwari": wm("Swargadwari.jpg"),
    "rara-lake": wm("Rara_Lake_Nepal.jpg"),
    "shey-phoksundo-lake": wm("Phoksundo_Lake.jpg"),
    "jumla": wm("Jumla_Valley.jpg"),
    "khaptad-national-park": wm("Khaptad_National_Park.jpg"),
    "badimalika-temple": wm("Badimalika.jpg"),
    "api-himal-base-camp": wm("Api_Himal.jpg"),
    "ghodaghodi-lake": wm("Ghodaghodi_Lake.jpg"),
}


PROVINCE_COVER: dict[str, str] = {
    "koshi": wm("Kangchenjunga_India.jpg"),
    "madhesh": wm("Janaki_Mandir.jpg"),
    "bagmati": wm("Boudhanath.jpg"),
    "gandaki": wm("Phewa_Lake_Pokhara.jpg"),
    "lumbini": wm("Mayadevi_Temple,_Lumbini.jpg"),
    "karnali": wm("Rara_Lake_Nepal.jpg"),
    "sudurpashchim": wm("Khaptad_National_Park.jpg"),
}


def gradient_for(keys) -> str:

    for key in keys:
        if key in CATEGORY_GRADIENT:
            return CATEGORY_GRADIENT[key]
    return CATEGORY_GRADIENT["_default"]



ICON_EMOJI: dict[str, str] = {
    "lake": "🌊", "temple": "🛕", "mountain": "🏔️", "wildlife": "🦏",
    "monument": "🏛️", "hill": "⛰️", "star": "⭐",
}


_NAME_ICONS = [
    ("lake", "lake"),
    ("temple", "temple"), ("mandir", "temple"), ("stupa", "temple"),
    ("pashupatinath", "temple"), ("muktinath", "temple"), ("swargadwari", "temple"),
    ("badimalika", "temple"), ("pathibhara", "temple"), ("gadhimai", "temple"),
    ("national park", "wildlife"), ("wildlife", "wildlife"),
    ("base camp", "mountain"), ("himal", "mountain"), ("everest", "mountain"),
    ("annapurna", "mountain"), ("kanchenjunga", "mountain"), ("poon hill", "mountain"),
    ("durbar", "monument"), ("square", "monument"), ("museum", "monument"),
    ("tansen", "monument"),
    ("hill", "hill"), ("sarangkot", "hill"), ("nagarkot", "hill"),
    ("khaptad", "hill"), ("ilam", "hill"),
]


_CATEGORY_ICON = {
    "religious": "temple", "trekking": "mountain", "hiking": "hill",
    "adventure": "wildlife", "historic": "monument", "popular": "star",
}


def icon_for(name: str, keys=()) -> str:

    low = (name or "").lower()
    for needle, icon in _NAME_ICONS:
        if needle in low:
            return icon
    for key in keys:  
        if key in _CATEGORY_ICON:
            return _CATEGORY_ICON[key]
    return "star"
