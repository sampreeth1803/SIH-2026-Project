from collections import defaultdict
from pathlib import Path
from typing import Optional

from detection import VEHICLE_CLASSES

MODEL_PATH = Path(__file__).resolve().parent / "yolo11n.pt"

CLASS_NAMES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def track_vehicles(
    video_path: Path,
    output_dir: Path,
    confidence: float = 0.25,
    road_roi: Optional[tuple[int, int, int, int]] = None,
):
    from ultralytics import YOLO

    model = YOLO(str(MODEL_PATH))
    results = model.track(
        source=str(video_path),
        tracker="bytetrack.yaml",
        save=True,
        conf=confidence,
        classes=VEHICLE_CLASSES,
        project=str(output_dir / "track"),
        name="vehicle_tracking",
        exist_ok=True,
    )

    unique_vehicles = defaultdict(set)
    occupancy_ratios = []
    for result in results:
        frame_height, frame_width = result.orig_shape
        x1, y1, x2, y2 = road_roi or (0, 0, frame_width, frame_height)
        x1 = max(0, min(x1, frame_width))
        y1 = max(0, min(y1, frame_height))
        x2 = max(x1 + 1, min(x2, frame_width))
        y2 = max(y1 + 1, min(y2, frame_height))
        road_area = (x2 - x1) * (y2 - y1)
        vehicle_area = 0.0

        if result.boxes is None:
            occupancy_ratios.append(0.0)
            continue

        classes = result.boxes.cls.cpu().numpy().astype(int)
        boxes = result.boxes.xyxy.cpu().numpy()
        track_ids = (
            result.boxes.id.cpu().numpy().astype(int)
            if result.boxes.id is not None
            else [None] * len(classes)
        )
        for track_id, class_id, box in zip(track_ids, classes, boxes):
            if class_id in CLASS_NAMES:
                if track_id is not None:
                    unique_vehicles[CLASS_NAMES[class_id]].add(track_id)
                box_x1, box_y1, box_x2, box_y2 = box
                intersection_width = max(
                    0, min(box_x2, x2) - max(box_x1, x1)
                )
                intersection_height = max(
                    0, min(box_y2, y2) - max(box_y1, y1)
                )
                vehicle_area += intersection_width * intersection_height

        occupancy_ratios.append(min(vehicle_area / road_area, 1.0))

    vehicle_counts = {name: int(len(ids)) for name, ids in unique_vehicles.items()}
    return {
        "vehicle_counts": vehicle_counts,
        "average_occupancy": float(
            sum(occupancy_ratios) / len(occupancy_ratios)
            if occupancy_ratios
            else 0.0
        ),
        "peak_occupancy": float(max(occupancy_ratios, default=0.0)),
    }
