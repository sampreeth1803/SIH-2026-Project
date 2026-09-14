from pathlib import Path

VEHICLE_CLASSES = [2, 3, 5, 7]
MODEL_PATH = Path(__file__).resolve().parent / "yolo11n.pt"


def detect_vehicles(video_path: Path, output_dir: Path, confidence: float = 0.25):
    from ultralytics import YOLO

    model = YOLO(str(MODEL_PATH))
    return model.predict(
        source=str(video_path),
        save=True,
        conf=confidence,
        classes=VEHICLE_CLASSES,
        project=str(output_dir / "detect"),
        name="vehicle_detection",
        exist_ok=True,
    )
