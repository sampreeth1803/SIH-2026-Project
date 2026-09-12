from __future__ import annotations

from pathlib import Path
import subprocess
from threading import Lock, Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from detection import detect_vehicles
from tracking import track_vehicles

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
VIDEO_PATH = BASE_DIR / "traffic_video.mp4"

CAMERAS = [
    {
        "id": "CAM-BLR-01",
        "name": "Outer Ring Road",
        "location": "Marathahalli Junction",
        "latitude": 12.9592,
        "longitude": 77.6974,
        "video_path": VIDEO_PATH,
        "metadata": "Simulated prerecorded feed",
        "road_roi": [0, 180, 1280, 720],
    },
    {
        "id": "CAM-BLR-02",
        "name": "Central Bengaluru",
        "location": "Majestic",
        "latitude": 12.9762,
        "longitude": 77.5713,
        "video_path": VIDEO_PATH,
        "metadata": "Simulated prerecorded feed",
        "road_roi": [0, 180, 1280, 720],
    },
    {
        "id": "CAM-BLR-03",
        "name": "Tech Corridor",
        "location": "Electronic City",
        "latitude": 12.8458,
        "longitude": 77.6603,
        "video_path": VIDEO_PATH,
        "metadata": "Simulated prerecorded feed",
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
    return {
        key: value
        for key, value in camera.items()
        if key != "video_path"
    } | {
        "video_url": f"/api/cameras/{camera['id']}/video",
        "tracked_video_url": f"/api/cameras/{camera['id']}/tracked-video",
    }


def tracked_video_path() -> Path | None:
    tracking_dir = OUTPUT_DIR / "track" / "vehicle_tracking"
    candidates = sorted(
        [*tracking_dir.glob("*.mp4"), *tracking_dir.glob("*.avi")],
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def run_tracking(job_id: str, camera: dict, confidence: float, road_roi: tuple[int, int, int, int] | None):
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        detect_vehicles(camera["video_path"], OUTPUT_DIR, confidence)
        traffic_data = track_vehicles(
            camera["video_path"], OUTPUT_DIR, confidence, road_roi
        )
        output_files = sorted(
            (OUTPUT_DIR / "track" / "vehicle_tracking").glob("*.avi"),
            key=lambda path: path.stat().st_mtime,
        )
        output_path = output_files[-1] if output_files else None
        if output_path:
            mp4_path = output_path.with_suffix(".mp4")
            conversion = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(output_path),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(mp4_path),
                ],
                capture_output=True,
                check=False,
            )
            if conversion.returncode == 0 and mp4_path.is_file():
                output_path = mp4_path
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
    output_path = tracked_video_path()
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
