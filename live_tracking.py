"""Opt-in, in-memory live traffic processing for configured camera sources."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "live_feeds.json"


class LiveFeedManager:
    def __init__(self):
        self._workers: dict[str, dict] = {}
        self._lock = Lock()

    def _configured_feeds(self) -> list[dict]:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def feeds(self) -> list[dict]:
        result = []
        for feed in self._configured_feeds()[:3]:
            worker = self._workers.get(feed.get("id", ""), {})
            has_page, has_stream = bool(feed.get("page_url")), bool(feed.get("stream_url"))
            enabled = bool(feed.get("enabled"))
            processing_ready = enabled and has_stream
            status = worker.get("status", "Ready" if processing_ready else "Viewing only")
            result.append({key: value for key, value in feed.items() if key != "stream_url"} | {
                "authorised": enabled and (has_page or has_stream), "processing_ready": processing_ready,
                "status": status, "error": worker.get("error"), "analytics": worker.get("analytics"), "last_frame_at": worker.get("last_frame_at"),
                "original_stream_url": f"/api/live-feeds/{feed.get('id')}/original.mjpeg" if status == "Running" else None,
                "tracked_stream_url": f"/api/live-feeds/{feed.get('id')}/tracked.mjpeg" if status == "Running" else None,
            })
        return result

    def start(self, feed_id: str) -> dict:
        raw = next((item for item in self._configured_feeds() if item.get("id") == feed_id), None)
        if not raw:
            raise ValueError("Live feed not found")
        if not raw.get("enabled"):
            raise PermissionError("This feed has been disabled in live_feeds.json")
        if not raw.get("stream_url"):
            raise PermissionError("This camera page is embedded for viewing. Add its authorised direct MJPEG, RTSP, or HLS stream URL to stream_url before enabling server-side tracking.")
        latitude, longitude = raw.get("latitude"), raw.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or (latitude == 0 and longitude == 0):
            raise PermissionError("Add valid Bengaluru latitude and longitude before enabling this production feed.")
        with self._lock:
            if self._workers.get(feed_id, {}).get("status") == "Running":
                return self._workers[feed_id]
            if sum(item.get("status") == "Running" for item in self._workers.values()) >= 3:
                raise RuntimeError("The prototype supports at most three simultaneous feeds")
            worker = {"status": "Starting", "error": None, "stop": Event(), "original": None, "tracked": None, "analytics": None, "last_frame_at": None, "source_url": raw["stream_url"]}
            self._workers[feed_id] = worker
            Thread(target=self._run, args=(worker,), daemon=True).start()
            return worker

    def stop(self, feed_id: str) -> None:
        if worker := self._workers.get(feed_id):
            worker["stop"].set()

    def frame(self, feed_id: str, kind: str):
        while True:
            worker = self._workers.get(feed_id)
            if not worker or worker.get("status") not in {"Starting", "Running"}:
                return
            if image := worker.get(kind):
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + image + b"\r\n"
            time.sleep(0.08)

    def _run(self, worker: dict) -> None:
        capture = None
        try:
            import cv2
            from ultralytics import YOLO
            capture = cv2.VideoCapture(worker["source_url"])
            if not capture.isOpened():
                raise RuntimeError("Could not open the configured media stream")
            model = YOLO(str(BASE_DIR / "yolo11n.pt"))
            worker["status"] = "Running"
            frames, started = 0, time.monotonic()
            while not worker["stop"].is_set():
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Camera stream ended or became unavailable")
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                worker["original"] = encoded.tobytes() if ok else None
                result = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=[2, 3, 5, 7], conf=0.25, verbose=False)[0]
                ok, encoded = cv2.imencode(".jpg", result.plot(), [cv2.IMWRITE_JPEG_QUALITY, 80])
                worker["tracked"] = encoded.tobytes() if ok else None
                frames += 1
                worker["last_frame_at"] = datetime.now(timezone.utc).isoformat()
                worker["analytics"] = {"tracker": "ByteTrack", "frames_processed": frames, "vehicles_in_latest_frame": len(result.boxes) if result.boxes is not None else 0, "processing_fps": round(frames / max(time.monotonic() - started, 0.001), 1)}
            worker["status"] = "Stopped"
        except Exception as exc:
            worker["status"], worker["error"] = "Failed", str(exc)
        finally:
            if capture is not None:
                capture.release()


live_feed_manager = LiveFeedManager()
