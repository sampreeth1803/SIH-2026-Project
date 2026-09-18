from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from anpr import best_plate_candidate
from camera_catalog import load_catalogue
from camera_registry import CameraRegistry
from detection import detect_vehicles
from india_registration import infer_indian_registration
from live_tracking import live_feed_manager
from privacy import anonymize_plate, normalize_plate
from tracking import track_vehicles
from tomtom_traffic import tomtom_traffic
from video_processing import convert_to_mp4, find_tracking_video

BASE_DIR = Path(__file__).resolve().parent
VIDEO_DIR = BASE_DIR / "videos"
OUTPUT_DIR = BASE_DIR / "output"
CATALOGUE_CAMERAS: list[dict] = []

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
camera_registry = CameraRegistry(BASE_DIR, CAMERAS)

jobs: dict[str, dict] = {}
jobs_lock = Lock()
app = FastAPI(title="CityPulse AI Traffic API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def refresh_bengaluru_catalogue() -> None:
    global CATALOGUE_CAMERAS
    CATALOGUE_CAMERAS = load_catalogue(refresh=True, count=100)


def public_camera(camera: dict) -> dict:
    manifest = camera_manifest(camera["id"])
    analytics = manifest.get("analytics") if manifest else None
    vehicle_count = sum((analytics or {}).get("vehicle_counts", {}).values()) if analytics else None
    source_available = bool(camera.get("source_available", camera.get("video_path", Path()).is_file()))
    processing_status = "Ready" if manifest else "Not precomputed"
    return {
        key: value
        for key, value in camera.items()
        if key not in {"video_path", "stream_source", "source_url", "stream_url", "source_env"}
    } | {
        "source_type": camera.get("source_type", "demo_video"),
        "stream_type": camera.get("stream_type", "mp4"),
        "enabled": camera.get("enabled", True),
        "source_available": source_available,
        "tracking_available": bool(camera.get("tracking_available", source_available)),
        "source_error": camera.get("source_error"),
        "source_attribution": "CityPulse local demonstration footage",
        "source_licence": "Local prototype asset",
        "video_available": source_available,
        "video_url": f"/api/cameras/{camera['id']}/video",
        "tracked_video_url": f"/api/cameras/{camera['id']}/tracked-video",
        "tracking_ready": manifest is not None,
        "analytics": analytics,
        "traffic_status": traffic_level(analytics),
        "alerts": analytics_alerts(camera["id"], analytics),
        "demo_status": "prerecorded source / precomputed analysis",
        "status": "Online" if source_available else "Offline",
        "processing_status": processing_status,
        "camera_health": "Healthy" if source_available else "Source unavailable",
        "last_updated": (analytics or {}).get("generated_at") if analytics else None,
        "fps": (analytics or {}).get("video_fps") or None,
        "video_quality": "Local MP4 source" if source_available else "Unavailable",
        "detection_confidence": manifest.get("confidence") if manifest else None,
        "vehicle_count": vehicle_count,
        "congestion_level": traffic_level(analytics),
    }


def catalogue_camera(camera: dict) -> dict:
    return camera | {
        "video_url": None, "tracked_video_url": None, "tracking_ready": False, "source_available": False, "tracking_available": False, "stream_type": "none",
        "analytics": None, "traffic_status": "Catalogue only", "alerts": [],
        "status": "Location only", "processing_status": "No authorised video source",
        "camera_health": "No video source assigned", "last_updated": None,
        "fps": None, "video_quality": "Unavailable", "detection_confidence": None,
        "vehicle_count": None, "congestion_level": "Unavailable",
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


def traffic_level(analytics: dict | None) -> str:
    if not analytics:
        return "Unavailable"
    average = float(analytics.get("average_occupancy", 0.0) or 0.0)
    peak = float(analytics.get("peak_occupancy", 0.0) or 0.0)
    if peak >= 0.5 or average >= 0.3:
        return "Severe"
    if peak >= 0.35 or average >= 0.2:
        return "Heavy"
    if peak >= 0.2 or average >= 0.1:
        return "Moderate"
    return "Low"


def analytics_alerts(camera_id: str, analytics: dict | None) -> list[dict]:
    if not analytics:
        return []

    alerts = []
    level = traffic_level(analytics)
    generated_at = analytics.get("generated_at") or datetime.now().astimezone().isoformat()
    average = float(analytics.get("average_occupancy", 0.0) or 0.0)
    peak = float(analytics.get("peak_occupancy", 0.0) or 0.0)
    peak_vehicles = int(analytics.get("peak_vehicles_in_frame", 0) or 0)

    if level in {"Heavy", "Severe"}:
        alerts.append(
            {
                "type": "congestion",
                "severity": "critical" if level == "Severe" else "high",
                "camera_id": camera_id,
                "timestamp": generated_at,
                "reason": f"{level} congestion detected: peak occupancy {peak:.1%}, average occupancy {average:.1%}.",
                "source": "tracking analytics",
            }
        )
    if peak_vehicles >= 8 and peak >= 0.2:
        alerts.append(
            {
                "type": "traffic_buildup",
                "severity": "medium",
                "camera_id": camera_id,
                "timestamp": generated_at,
                "reason": f"Traffic buildup reached {peak_vehicles} vehicles in one frame with {peak:.1%} peak occupancy.",
                "source": "tracking analytics",
            }
        )
    return alerts


def tracked_video_path(camera_id: str) -> Path | None:
    manifest = camera_manifest(camera_id)
    if manifest:
        return OUTPUT_DIR / "cameras" / camera_id / manifest["tracked_video"]
    return find_tracking_video(
        OUTPUT_DIR / "cameras" / camera_id / "track" / "vehicle_tracking"
    )


def _time_to_decimal(time_value: str | None) -> float:
    if not time_value:
        return 12.0
    try:
        hour_text, minute_text = str(time_value).split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        return hour + minute / 60.0
    except (TypeError, ValueError):
        return 12.0


def _segment_distance_km(camera_a: dict, camera_b: dict) -> float:
    lat1 = math.radians(camera_a["latitude"])
    lat2 = math.radians(camera_b["latitude"])
    delta_lat = math.radians(camera_b["latitude"] - camera_a["latitude"])
    delta_lon = math.radians(camera_b["longitude"] - camera_a["longitude"])
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371.0 * c


def estimate_camera_congestion(camera: dict, time_value: str | None = None, analytics: dict | None = None) -> float:
    manifest = camera_manifest(camera["id"])
    camera_analytics = (analytics or manifest.get("analytics") if manifest else analytics or {}) or {}
    avg_occupancy = float(camera_analytics.get("average_occupancy", 0.0) or 0.0)
    peak_occupancy = float(camera_analytics.get("peak_occupancy", 0.0) or 0.0)
    vehicle_counts = camera_analytics.get("vehicle_counts") or {}
    total_vehicles = sum(int(count) for count in vehicle_counts.values())

    base_score = 0.55 * avg_occupancy + 0.45 * peak_occupancy
    if total_vehicles:
        base_score = min(1.0, base_score + min(0.25, total_vehicles / 100.0))

    hour = _time_to_decimal(time_value)
    if 7.0 <= hour < 10.0 or 17.0 <= hour < 20.0:
        time_factor = 1.25
    elif 10.0 <= hour < 17.0:
        time_factor = 1.05
    elif 20.0 <= hour < 23.0 or 0.0 <= hour < 6.0:
        time_factor = 0.8
    else:
        time_factor = 0.9

    predicted = min(1.0, max(0.0, base_score * time_factor))
    return round(predicted, 4)


def route_candidates(start_camera: dict, end_camera: dict):
    if start_camera["id"] == end_camera["id"]:
        return [[start_camera["id"]]]

    adjacency = {
        camera["id"]: [] for camera in CAMERAS
    }
    for index, camera in enumerate(CAMERAS):
        for other in CAMERAS[index + 1:]:
            distance = _segment_distance_km(camera, other)
            if distance < 3.5:
                adjacency[camera["id"]].append((other["id"], distance))
                adjacency[other["id"]].append((camera["id"], distance))

    for camera in CAMERAS:
        if camera["id"] not in adjacency:
            adjacency[camera["id"]] = []

    visited = {start_camera["id"]: [start_camera["id"]]}
    queue = [start_camera["id"]]
    while queue:
        current = queue.pop(0)
        for neighbor, _ in adjacency.get(current, []):
            if neighbor in visited:
                continue
            visited[neighbor] = visited[current] + [neighbor]
            if neighbor == end_camera["id"]:
                return [visited[neighbor]]
            queue.append(neighbor)

    return [[start_camera["id"], end_camera["id"]]]


def _segment_congestion_color(value: float) -> str:
    if value >= 0.7:
        return "#ff4d4d"
    if value >= 0.45:
        return "#ffb347"
    return "#34d399"


def predict_route(from_camera_id: str, to_camera_id: str, time_value: str | None = None) -> dict:
    start_camera = next((item for item in CAMERAS if item["id"] == from_camera_id), None)
    end_camera = next((item for item in CAMERAS if item["id"] == to_camera_id), None)
    if start_camera is None or end_camera is None:
        raise ValueError("Start and destination cameras must be valid camera IDs")

    route = route_candidates(start_camera, end_camera)[0]
    congestion_scores = []
    segment_congestion = []
    for camera_id in route:
        camera = next((item for item in CAMERAS if item["id"] == camera_id), None)
        if camera is None:
            continue
        manifest = camera_manifest(camera["id"])
        analytics = manifest.get("analytics") if manifest else None
        score = estimate_camera_congestion(camera, time_value, analytics)
        congestion_scores.append(score)

    for current_id, next_id in zip(route, route[1:]):
        current = next(item for item in CAMERAS if item["id"] == current_id)
        nxt = next(item for item in CAMERAS if item["id"] == next_id)
        current_score = estimate_camera_congestion(current, time_value, camera_manifest(current["id"]).get("analytics") if camera_manifest(current["id"]) else None)
        next_score = estimate_camera_congestion(nxt, time_value, camera_manifest(nxt["id"]).get("analytics") if camera_manifest(nxt["id"]) else None)
        segment_value = round((current_score + next_score) / 2.0, 4)
        segment_congestion.append(
            {
                "from": current_id,
                "to": next_id,
                "congestion": segment_value,
                "color": _segment_congestion_color(segment_value),
                "label": "Peak congestion" if segment_value >= 0.7 else "Moderate" if segment_value >= 0.45 else "Free flow",
            }
        )

    total_distance_km = 0.0
    for current_id, next_id in zip(route, route[1:]):
        current = next(item for item in CAMERAS if item["id"] == current_id)
        nxt = next(item for item in CAMERAS if item["id"] == next_id)
        total_distance_km += _segment_distance_km(current, nxt)

    average_congestion = sum(congestion_scores) / len(congestion_scores) if congestion_scores else 0.0
    # Convert the camera-to-camera distance into an urban driving estimate. The
    # previous multiplier treated every kilometer as twelve minutes, which made
    # short neighborhood routes look like cross-city journeys.
    road_distance_km = total_distance_km * 1.25
    free_flow_speed_kph = 32.0
    congestion_speed_kph = max(12.0, free_flow_speed_kph * (1.0 - 0.55 * average_congestion))
    drive_minutes = (road_distance_km / congestion_speed_kph) * 60.0
    signal_delay_minutes = max(0, len(route) - 2) * (0.5 + average_congestion * 1.5)
    travel_minutes = round(max(1.0, drive_minutes + signal_delay_minutes), 1)

    return {
        "from": start_camera["id"],
        "to": end_camera["id"],
        "route": route,
        "route_names": [next(item["name"] for item in CAMERAS if item["id"] == camera_id) for camera_id in route],
        "time": time_value or "12:00",
        "average_congestion": round(average_congestion, 4),
        "estimated_travel_minutes": travel_minutes,
        "segment_congestion": segment_congestion,
        "best_route_reason": (
            "Lower traffic load and shorter distance path at this time window"
            if average_congestion < 0.45
            else "Route is under peak congestion; consider off-peak alternatives"
            if average_congestion >= 0.7
            else "Route is under moderate congestion; consider off-peak alternatives"
        ),
    }


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
                traffic_status=traffic_level(traffic_data),
                alerts=analytics_alerts(camera["id"], traffic_data),
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
    available_cameras = sum(camera["video_path"].is_file() for camera in CAMERAS)
    ready_cameras = sum(camera_manifest(camera["id"]) is not None for camera in CAMERAS)
    return {
        "status": "ok",
        "simulated": True,
        "backend": "online",
        "model": "available" if (BASE_DIR / "yolo11n.pt").is_file() else "missing",
        "camera_sources": f"{available_cameras}/{len(CAMERAS)} available",
        "precomputed_cameras": f"{ready_cameras}/{len(CAMERAS)} ready",
        "active_jobs": sum(job.get("status") == "running" for job in jobs.values()),
        "tomtom_traffic": "configured" if tomtom_traffic.configured else "not configured",
        "last_successful_processing": max(
            (camera_manifest(camera["id"]).get("generated_at", "") for camera in CAMERAS if camera_manifest(camera["id"])),
            default=None,
        ),
    }


@app.get("/api/cameras")
def list_cameras():
    result = []
    for camera in registry_cameras():
        result.append(catalogue_camera(camera) if camera.get("source_type") == "catalogue" else public_camera(camera))
    return result


@app.get("/api/cameras/{camera_id}")
def get_camera(camera_id: str):
    camera = traffic_camera_by_id(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return catalogue_camera(camera) if camera.get("source_type") == "catalogue" else public_camera(camera)


def traffic_camera_by_id(camera_id: str) -> dict | None:
    return camera_registry.get_camera(camera_id, CATALOGUE_CAMERAS)


def registry_cameras() -> list[dict]:
    return camera_registry.all_cameras(CATALOGUE_CAMERAS)


@app.get("/api/traffic/cameras")
def list_camera_traffic():
    cameras = registry_cameras()
    tomtom_traffic.refresh_all_async(cameras)
    traffic = [tomtom_traffic.cached_camera_traffic(camera) for camera in cameras]
    return {
        "provider": "TomTom Traffic Flow",
        "refresh_seconds": tomtom_traffic.ttl_seconds,
        "cameras": [
            {"camera_id": camera["id"], "latitude": camera["latitude"], "longitude": camera["longitude"]} | item
            for camera, item in zip(cameras, traffic)
        ],
    }


@app.get("/api/traffic/cameras/{camera_id}")
def camera_traffic(camera_id: str):
    camera = traffic_camera_by_id(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"camera_id": camera_id, "latitude": camera["latitude"], "longitude": camera["longitude"]} | tomtom_traffic.camera_traffic(camera)


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


@app.get("/api/predict-route")
def predict_route_api(from_camera: str, to_camera: str, time: str | None = None):
    try:
        return predict_route(from_camera, to_camera, time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/predict-traffic")
def predict_traffic_api(camera_id: str, horizons: str = "15,30,60"):
    camera = next((item for item in CAMERAS if item["id"] == camera_id), None)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    manifest = camera_manifest(camera_id)
    analytics = manifest.get("analytics") if manifest else None
    if not analytics:
        raise HTTPException(status_code=404, detail="Traffic prediction requires precomputed analytics")

    base_count = int(sum(analytics.get("vehicle_counts", {}).values()))
    base_congestion = estimate_camera_congestion(camera, datetime.now().strftime("%H:%M"), analytics)
    predictions = []
    for raw_horizon in horizons.split(","):
        try:
            horizon = int(raw_horizon)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Prediction horizons must be integers") from exc
        if horizon not in {15, 30, 60}:
            raise HTTPException(status_code=400, detail="Supported prediction horizons are 15, 30, and 60 minutes")
        growth = 1.0 + (0.04 * horizon / 15.0 if base_congestion >= 0.45 else -0.02 * horizon / 15.0)
        predicted_count = max(0, round(base_count * growth))
        predicted_congestion = min(1.0, round(base_congestion * (1.0 + horizon / 500.0), 4))
        predictions.append(
            {
                "horizon_minutes": horizon,
                "traffic_level": traffic_level({"average_occupancy": predicted_congestion, "peak_occupancy": predicted_congestion}),
                "predicted_vehicle_count": predicted_count,
                "congestion": predicted_congestion,
                "confidence": "low",
                "trend": "rising" if predicted_congestion > base_congestion else "easing" if predicted_congestion < base_congestion else "stable",
            }
        )
    return {
        "camera_id": camera_id,
        "model": "Estimated baseline prediction",
        "source": "precomputed occupancy and vehicle counts; no historical model available",
        "predictions": predictions,
    }


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
            "traffic_status": "Processing",
            "alerts": [],
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


def _tracking_camera(camera_id: str) -> dict:
    camera = traffic_camera_by_id(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@app.get("/api/cameras/{camera_id}/status")
@app.get("/api/cameras/{camera_id}/tracking")
def tracking_status(camera_id: str):
    _tracking_camera(camera_id)
    return live_feed_manager.status(camera_id)


@app.post("/api/cameras/{camera_id}/tracking/start")
def start_camera_tracking(camera_id: str):
    camera = _tracking_camera(camera_id)
    try:
        return live_feed_manager.start(camera)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/cameras/{camera_id}/tracking/stop")
def stop_camera_tracking(camera_id: str):
    _tracking_camera(camera_id)
    live_feed_manager.stop(camera_id)
    return {"camera_id": camera_id, "status": "Stopping"}


@app.get("/api/cameras/{camera_id}/stream")
def camera_stream(camera_id: str, view: str = "tracked"):
    _tracking_camera(camera_id)
    if view not in {"original", "tracked"}:
        raise HTTPException(status_code=400, detail="view must be original or tracked")
    return StreamingResponse(live_feed_manager.frame(camera_id, view), media_type="multipart/x-mixed-replace; boundary=frame")


# Compatibility routes for the existing Live Tracking page and bookmarked demos.
@app.get("/api/live-feeds")
def list_live_feeds():
    return [public_camera(camera) | {"traffic": tomtom_traffic.camera_traffic(camera), **live_feed_manager.status(camera["id"])} for camera in registry_cameras() if camera.get("source_type") in {"demo", "configured"}]


@app.post("/api/live-feeds/{feed_id}/start")
def start_live_feed(feed_id: str):
    return start_camera_tracking(feed_id)


@app.post("/api/live-feeds/{feed_id}/stop")
def stop_live_feed(feed_id: str):
    return stop_camera_tracking(feed_id)


@app.get("/api/live-feeds/{feed_id}/{kind}.mjpeg")
def live_feed_stream(feed_id: str, kind: str):
    return camera_stream(feed_id, "tracked" if kind == "tracked" else "original")


@app.post("/api/anpr/recognize")
async def recognize_plate(request: Request):
    try:
        form = await request.form()
    except AssertionError as exc:
        raise HTTPException(status_code=503, detail="Install python-multipart to enable image uploads") from exc
    image = form.get("image")
    confirmed_plate = form.get("confirmed_plate")
    if image is None or not hasattr(image, "read"):
        raise HTTPException(status_code=400, detail="An image upload is required")
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
    contents = await image.read()
    if not contents or len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be between 1 byte and 5 MB")
    suffix = Path(image.filename or "plate.jpg").suffix or ".jpg"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        candidate = best_plate_candidate(temporary_path)
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
    if not candidate:
        return {"candidate": None, "requires_confirmation": True, "result": None,
                "message": "No reliable plate text was found. Upload a sharper, front-facing image."}
    if not confirmed_plate:
        return {"candidate": candidate, "requires_confirmation": True, "result": None,
                "message": "Review or correct the OCR result before registration-area lookup."}
    confirmed = normalize_plate(confirmed_plate)
    if len(confirmed) < 4 or len(confirmed) > 14:
        raise HTTPException(status_code=400, detail="Confirmed plate text must contain 4 to 14 letters or digits")
    masked = f"{confirmed[:2]}***{confirmed[-3:]}" if len(confirmed) > 5 else "***"
    return {"candidate": candidate, "requires_confirmation": False,
            "result": {"plate_masked": masked, "plate_id": anonymize_plate(confirmed),
                       "registration": infer_indian_registration(confirmed), "sightings": []},
            "message": "No verified camera sightings are stored in this upload-only release."}
