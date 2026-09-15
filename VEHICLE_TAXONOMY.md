# CityPulse Vehicle Taxonomy

CityPulse uses a 14-class vehicle taxonomy:

| ID | Class | Description |
|---:|---|---|
| 1 | Hatchback | Small passenger car without a protruding rear boot. |
| 2 | Sedan | Passenger car with a separate protruding rear boot. |
| 3 | SUV | High-clearance car-like vehicle without a protruding boot. |
| 4 | MUV | Large multi-row passenger and cargo vehicle. |
| 5 | Bus | Large public or private passenger vehicle. |
| 6 | Truck | Heavy goods carrier with a front cabin and cargo compartment. |
| 7 | Three-wheeler | Covered vehicle with one front wheel and two rear wheels. |
| 8 | Two-wheeler | Motorbike or scooter; the box includes the vehicle and rider. |
| 9 | LCV | Light commercial goods carrier. |
| 10 | Mini-bus | Compact bus with fewer seats than a full-size bus. |
| 11 | Tempo-traveller | Medium passenger van with a tall roof. |
| 12 | Bicycle | Manually pedalled cycle; the box includes the vehicle and rider. |
| 13 | Van | Medium goods or passenger vehicle with a flat front. |
| 14 | Other | Agricultural, specialised, or otherwise unclassified vehicle. |

## Model compatibility

`vehicle_classes.py` is the single source of truth for class names, IDs, aliases, and model-label normalization. Detection and tracking inspect the loaded YOLO model's class names automatically.

The bundled `yolo11n.pt` is COCO-trained. It directly supports `car`, `motorcycle`, `bus`, and `truck`; these remain available for the current demonstration. A YOLO model trained with the 14 taxonomy labels can be supplied in the same model path and will be detected automatically. The application normalizes `motorcycle`, `motorbike`, and `scooter` to `two-wheeler` for taxonomy-trained models.

This distinction is important: a COCO car detection cannot be truthfully split into hatchback, sedan, SUV, or MUV without taxonomy-labelled training data.

The taxonomy is available from `GET /api/vehicle-classes` and is included in each camera response as `vehicle_class_taxonomy`.
