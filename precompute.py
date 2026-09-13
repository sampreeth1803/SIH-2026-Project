from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from api import CAMERAS, OUTPUT_DIR
from tracking import track_vehicles
from video_processing import convert_to_mp4, find_tracking_video


def camera_output_dir(camera_id: str) -> Path:
    return OUTPUT_DIR / "cameras" / camera_id


def manifest_path(camera_id: str) -> Path:
    return camera_output_dir(camera_id) / "manifest.json"


def precompute_camera(camera: dict, confidence: float, force: bool) -> dict:
    output_dir = camera_output_dir(camera["id"])
    manifest = manifest_path(camera["id"])
    tracked_mp4 = output_dir / "tracked.mp4"

    if not force and manifest.is_file() and tracked_mp4.is_file():
        print(f"{camera['id']}: already ready (use --force to rebuild)")
        return json.loads(manifest.read_text(encoding="utf-8"))

    if force and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"{camera['id']}: tracking {camera['video_path'].name}")
    analytics = track_vehicles(
        camera["video_path"],
        output_dir,
        confidence,
        tuple(camera["road_roi"]),
    )
    source_video = find_tracking_video(output_dir / "track" / "vehicle_tracking")
    if source_video is None:
        raise RuntimeError(f"{camera['id']}: YOLO did not produce a tracking video")

    final_video = convert_to_mp4(source_video, tracked_mp4)
    payload = {
        "camera_id": camera["id"],
        "source_video": str(camera["video_path"].relative_to(OUTPUT_DIR.parent)),
        "tracked_video": str(final_video.relative_to(output_dir)),
        "confidence": confidence,
        "road_roi": camera["road_roi"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics": analytics,
    }
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"{camera['id']}: ready -> {final_video}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute tracking for all CityPulse cameras")
    parser.add_argument("--camera-id", action="append", help="Only process this camera ID; repeat for multiple cameras")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--force", action="store_true", help="Rebuild existing camera artifacts")
    args = parser.parse_args()

    selected_ids = set(args.camera_id or [camera["id"] for camera in CAMERAS])
    unknown_ids = selected_ids - {camera["id"] for camera in CAMERAS}
    if unknown_ids:
        parser.error(f"Unknown camera ID(s): {', '.join(sorted(unknown_ids))}")

    for camera in CAMERAS:
        if camera["id"] in selected_ids:
            precompute_camera(camera, args.confidence, args.force)


if __name__ == "__main__":
    main()
