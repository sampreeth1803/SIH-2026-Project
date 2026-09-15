"""Canonical vehicle taxonomy and model-label normalization for CityPulse."""

VEHICLE_TAXONOMY = [
    {"id": 1, "name": "hatchback", "description": "Small passenger car without a protruding rear boot."},
    {"id": 2, "name": "sedan", "description": "Passenger car with a separate protruding rear boot."},
    {"id": 3, "name": "suv", "description": "High-clearance car-like vehicle without a protruding boot."},
    {"id": 4, "name": "muv", "description": "Large multi-row passenger and cargo vehicle."},
    {"id": 5, "name": "bus", "description": "Large public or private passenger vehicle."},
    {"id": 6, "name": "truck", "description": "Heavy goods carrier with a front cabin and cargo compartment."},
    {"id": 7, "name": "three-wheeler", "description": "Covered vehicle with one front wheel and two rear wheels."},
    {"id": 8, "name": "two-wheeler", "description": "Motorbike or scooter; box includes the vehicle and rider."},
    {"id": 9, "name": "lcv", "description": "Light commercial goods carrier."},
    {"id": 10, "name": "mini-bus", "description": "Compact bus with fewer seats than a full-size bus."},
    {"id": 11, "name": "tempo-traveller", "description": "Medium passenger van with a tall roof."},
    {"id": 12, "name": "bicycle", "description": "Manually pedalled cycle; box includes the vehicle and rider."},
    {"id": 13, "name": "van", "description": "Medium goods or passenger vehicle with a flat front."},
    {"id": 14, "name": "other", "description": "Agricultural, specialised, or otherwise unclassified vehicle."},
]

TAXONOMY_NAMES = {item["name"] for item in VEHICLE_TAXONOMY}

ALIASES = {
    "motorcycle": "two-wheeler",
    "motorbike": "two-wheeler",
    "scooter": "two-wheeler",
    "three wheeler": "three-wheeler",
    "auto": "three-wheeler",
    "autorickshaw": "three-wheeler",
    "rickshaw": "three-wheeler",
    "minibus": "mini-bus",
    "mini bus": "mini-bus",
    "tempo traveller": "tempo-traveller",
    "tempo_traveller": "tempo-traveller",
    "light commercial vehicle": "lcv",
    "cycle": "bicycle",
}

# The bundled yolo11n.pt is COCO-trained. These IDs are retained as a
# compatibility fallback until a taxonomy-trained weights file is supplied.
COCO_CLASS_NAMES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
COCO_CLASS_IDS = list(COCO_CLASS_NAMES)


def canonical_class_name(label: str) -> str | None:
    normalized = str(label).strip().lower().replace("_", " ")
    if normalized in TAXONOMY_NAMES:
        return normalized
    return ALIASES.get(normalized)


def model_class_name(names: dict | list, class_id: int) -> str | None:
    """Resolve a model class to the canonical taxonomy when possible."""
    label = names.get(class_id, "") if isinstance(names, dict) else names[class_id]
    canonical = canonical_class_name(label)
    if canonical:
        return canonical
    if class_id in COCO_CLASS_NAMES:
        return COCO_CLASS_NAMES[class_id]
    return None


def model_vehicle_class_ids(names: dict | list) -> list[int]:
    """Select taxonomy classes for custom weights, or COCO vehicles as fallback."""
    ids = []
    iterable = names.items() if isinstance(names, dict) else enumerate(names)
    for class_id, label in iterable:
        if canonical_class_name(label) or class_id in COCO_CLASS_IDS:
            ids.append(int(class_id))
    return ids or COCO_CLASS_IDS
