from __future__ import annotations

import json
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from detection import detect_vehicles
from tracking import track_vehicles
from video_processing import convert_to_mp4, find_tracking_video

BASE_DIR = Path(__file__).resolve().parent
VIDEO_DIR = BASE_DIR / "videos"
OUTPUT_DIR = BASE_DIR / "output"

CAMERAS = [
    {
        "id": "CAM-BLR-01",
        "name": "Bangalore University Road",
        "location": "Jnanabharathi",
        "latitude": 12.935609,
        "longitude": 77.512984,
        "video_path": VIDEO_DIR / "cam_blr_01.mp4",
        "metadata": "Camera 01 feed",
        "road_roi": [0, 180, 1280, 720],
    },
    {
        "id": "CAM-BLR-02",
        "name": "Rajarajeshwarinagara Gate",
        "location": "Mysore Road",
        "latitude": 12.936354,
        "longitude": 77.518235,
        "video_path": VIDEO_DIR / "cam_blr_02.mp4",
        "metadata": "Camera 02 feed",
        "road_roi": [0, 180, 1280, 720],
    },
    {
        "id": "CAM-BLR-03",
        "name": "Bank of Baroda Junction",
        "location": "Adjacent to RR Nagar Petrol Bunk",
        "latitude": 12.932737,
        "longitude": 77.516147,
        "video_path": VIDEO_DIR / "cam_blr_03.mp4",
        "metadata": "Camera 03 feed",
        "road_roi": [0, 180, 1280, 720],
    },
    {
        "id": "CAM-BLR-04",
        "name": "Magadi Road Junction",
        "location": "Under the bridge near Magadi Road",
        "latitude": 12.945277,
        "longitude": 77.527680,
        "video_path": VIDEO_DIR / "cam_blr_04.mp4",
        "metadata": "Camera 04 feed",
        "road_roi": [0, 180, 1280, 720],
    },
]

jobs: dict[str, dict] = {}
jobs_lock = Lock()
app = FastAPI(title="CityPulse AI Traffic API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def public_camera(camera: dict) -> dict:
    manifest = camera_manifest(camera["id"])
    return {
        key: value
        for key, value in camera.items()
        if key != "video_path"
    } | {
        "video_url": f"/api/cameras/{camera['id']}/video",
        "tracked_video_url": f"/api/cameras/{camera['id']}/tracked-video",
        "tracking_ready": manifest is not None,
        "analytics": manifest.get("analytics") if manifest else None,
    }


def camera_manifest(camera_id: str) -> dict | None:
    manifest_path = OUTPUT_DIR / "cameras" / camera_id / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    tracked_path = OUTPUT_DIR / "cameras" / camera_id / manifest.get("tracked_video", "")
    return manifest if tracked_path.is_file() else None


def tracked_video_path(camera_id: str) -> Path | None:
    manifest = camera_manifest(camera_id)
    if manifest:
        return OUTPUT_DIR / "cameras" / camera_id / manifest["tracked_video"]
    return find_tracking_video(
        OUTPUT_DIR / "cameras" / camera_id / "track" / "vehicle_tracking"
    )


def run_tracking(job_id: str, camera: dict, confidence: float, road_roi: tuple[int, int, int, int] | None):
    try:
        camera_output_dir = OUTPUT_DIR / "cameras" / camera["id"]
        camera_output_dir.mkdir(parents=True, exist_ok=True)
        detect_vehicles(camera["video_path"], camera_output_dir, confidence)
        traffic_data = track_vehicles(
            camera["video_path"], camera_output_dir, confidence, road_roi
        )
        output_path = find_tracking_video(
            camera_output_dir / "track" / "vehicle_tracking"
        )
        if output_path:
            output_path = convert_to_mp4(
                output_path, camera_output_dir / "tracked.mp4"
            )
        with jobs_lock:
            jobs[job_id].update(
                status="completed",
                analytics=traffic_data,
                video_url=(
                    f"/api/jobs/{job_id}/video" if output_path else None
                ),
            )
            if output_path:
                jobs[job_id]["output_path"] = output_path
    except Exception as error:
        with jobs_lock:
            jobs[job_id].update(status="failed", error=str(error))


@app.get("/api/health")
def health():
    return {"status": "ok", "simulated": True}


@app.get("/api/cameras")
def list_cameras():
    return [public_camera(camera) for camera in CAMERAS]


@app.get("/api/cameras/{camera_id}/video")
def camera_video(camera_id: str):
    camera = next((item for item in CAMERAS if item["id"] == camera_id), None)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not camera["video_path"].is_file():
        raise HTTPException(status_code=404, detail="Video source is unavailable")
    return FileResponse(camera["video_path"], media_type="video/mp4")


@app.get("/api/cameras/{camera_id}/tracked-video")
def tracked_camera_video(camera_id: str):
    camera = next((item for item in CAMERAS if item["id"] == camera_id), None)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    output_path = tracked_video_path(camera_id)
    if output_path is None:
        raise HTTPException(
            status_code=404,
            detail="Tracked video is unavailable. Run main.py once to create it.",
        )
    media_type = "video/mp4" if output_path.suffix.lower() == ".mp4" else "video/x-msvideo"
    return FileResponse(output_path, media_type=media_type)


@app.post("/api/cameras/{camera_id}/tracking")
def start_tracking(
    camera_id: str,
    confidence: float = 0.25,
    x1: int | None = None,
    y1: int | None = None,
    x2: int | None = None,
    y2: int | None = None,
):
    camera = next((item for item in CAMERAS if item["id"] == camera_id), None)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if not camera["video_path"].is_file():
        raise HTTPException(status_code=404, detail="Video source is unavailable")

    road_roi = tuple(camera["road_roi"])
    roi_values = (x1, y1, x2, y2)
    if any(value is not None for value in roi_values):
        if any(value is None for value in roi_values):
            raise HTTPException(status_code=400, detail="All ROI coordinates are required")
        road_roi = (x1, y1, x2, y2)

    job_id = str(uuid4())
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "camera_id": camera_id,
            "status": "running",
            "analytics": None,
            "video_url": None,
            "error": None,
        }
    Thread(
        target=run_tracking,
        args=(job_id, camera, confidence, road_roi),
        daemon=True,
    ).start()
    return jobs[job_id]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Tracking job not found")
    return {key: value for key, value in job.items() if key != "output_path"}


@app.get("/api/jobs/{job_id}/video")
def job_video(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if job is None or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Processed video is not ready")
    output_path = job.get("output_path")
    if not output_path or not output_path.is_file():
        raise HTTPException(status_code=404, detail="Processed video is unavailable")
    media_type = "video/mp4" if output_path.suffix.lower() == ".mp4" else "video/x-msvideo"
    return FileResponse(output_path, media_type=media_type)
