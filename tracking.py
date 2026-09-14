from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2

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

    capture = cv2.VideoCapture(str(video_path))
    video_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    capture.release()

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
    vehicles_per_frame = []
    trend = []
    for frame_index, result in enumerate(results):
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
            vehicles_per_frame.append(0)
            if frame_index % 30 == 0:
                trend.append({"frame": frame_index, "vehicles": 0, "occupancy": 0.0})
            continue

        classes = result.boxes.cls.cpu().numpy().astype(int)
        boxes = result.boxes.xyxy.cpu().numpy()
        track_ids = (
            result.boxes.id.cpu().numpy().astype(int)
            if result.boxes.id is not None
            else [None] * len(classes)
        )
        current_vehicle_count = 0
        for track_id, class_id, box in zip(track_ids, classes, boxes):
            if class_id in CLASS_NAMES:
                current_vehicle_count += 1
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
        vehicles_per_frame.append(current_vehicle_count)
        if frame_index % 30 == 0:
            trend.append(
                {
                    "frame": frame_index,
                    "vehicles": current_vehicle_count,
                    "occupancy": round(occupancy_ratios[-1], 4),
                }
            )

    vehicle_counts = {
        name: int(len(unique_vehicles.get(name, set()))) for name in CLASS_NAMES.values()
    }
    frame_count = len(occupancy_ratios)
    average_vehicles = sum(vehicles_per_frame) / len(vehicles_per_frame) if vehicles_per_frame else 0.0
    duration_minutes = frame_count / video_fps / 60.0 if video_fps > 0 else 0.0
    vehicles_per_minute = (
        sum(vehicle_counts.values()) / duration_minutes if duration_minutes > 0 else 0.0
    )
    return {
        "vehicle_counts": vehicle_counts,
        "average_occupancy": float(
            sum(occupancy_ratios) / len(occupancy_ratios)
            if occupancy_ratios
            else 0.0
        ),
        "peak_occupancy": float(max(occupancy_ratios, default=0.0)),
        "frame_count": frame_count,
        "video_fps": video_fps,
        "average_vehicles_per_frame": round(average_vehicles, 3),
        "peak_vehicles_in_frame": max(vehicles_per_frame, default=0),
        "vehicles_per_minute": round(vehicles_per_minute, 2),
        "trend": trend,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
