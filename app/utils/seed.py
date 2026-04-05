from datetime import datetime

SEED_CATEGORIES = [
    {"name": "Plumber", "slug": "plumber", "sort_order": 1},
    {"name": "Electrician", "slug": "electrician", "sort_order": 2},
    {"name": "Carpenter", "slug": "carpenter", "sort_order": 3},
    {"name": "Painter", "slug": "painter", "sort_order": 4},
    {"name": "Mason / Mistri", "slug": "mason", "sort_order": 5},
    {"name": "Labour / Helper", "slug": "labour", "sort_order": 6},
    {"name": "AC Repair", "slug": "ac-repair", "sort_order": 7},
    {"name": "RO Repair", "slug": "ro-repair", "sort_order": 8},
    {"name": "CCTV Technician", "slug": "cctv", "sort_order": 9},
    {"name": "Welder", "slug": "welder", "sort_order": 10},
    {"name": "Tile Worker", "slug": "tile-worker", "sort_order": 11},
    {"name": "POP / False Ceiling", "slug": "pop-false-ceiling", "sort_order": 12},
    {"name": "House Cleaning", "slug": "house-cleaning", "sort_order": 13},
    {"name": "Appliance Repair", "slug": "appliance-repair", "sort_order": 14},
    {"name": "Pest Control", "slug": "pest-control", "sort_order": 15},
    {"name": "Furniture Work", "slug": "furniture", "sort_order": 16},
    {"name": "Borewell / Water Tank", "slug": "borewell", "sort_order": 17},
    {"name": "Civil Contractor", "slug": "civil-contractor", "sort_order": 18},
    {"name": "Interior Work", "slug": "interior", "sort_order": 19},
    {"name": "Packer / Mover Helper", "slug": "packer-mover", "sort_order": 20},
]

SEED_SUBCATEGORIES = {
    "plumber": [
        {"name": "Tap Repair", "slug": "tap-repair"},
        {"name": "Bathroom Fitting", "slug": "bathroom-fitting"},
        {"name": "Pipeline Repair", "slug": "pipeline-repair"},
        {"name": "Water Motor Issue", "slug": "water-motor"},
    ],
    "electrician": [
        {"name": "Fan Fitting", "slug": "fan-fitting"},
        {"name": "Switch Board Repair", "slug": "switchboard"},
        {"name": "Wiring", "slug": "wiring"},
        {"name": "Inverter Fitting", "slug": "inverter"},
        {"name": "Meter Issue", "slug": "meter-issue"},
    ],
    "carpenter": [
        {"name": "Furniture Repair", "slug": "furniture-repair"},
        {"name": "Door/Window Work", "slug": "door-window"},
        {"name": "Cabinet Making", "slug": "cabinet"},
    ],
    "painter": [
        {"name": "Interior Painting", "slug": "interior-painting"},
        {"name": "Exterior Painting", "slug": "exterior-painting"},
        {"name": "Texture/Design", "slug": "texture-design"},
    ],
}


async def seed_categories(db) -> None:
    existing = await db.categories.count_documents({})
    if existing > 0:
        return

    now = datetime.utcnow()
    category_id_map = {}

    for cat in SEED_CATEGORIES:
        doc = {**cat, "icon_url": None, "is_active": True, "created_at": now}
        result = await db.categories.insert_one(doc)
        category_id_map[cat["slug"]] = result.inserted_id

    for cat_slug, subcats in SEED_SUBCATEGORIES.items():
        cat_id = category_id_map.get(cat_slug)
        if not cat_id:
            continue
        for sub in subcats:
            doc = {
                **sub,
                "category_id": cat_id,
                "is_active": True,
                "created_at": now,
            }
            await db.subcategories.insert_one(doc)
