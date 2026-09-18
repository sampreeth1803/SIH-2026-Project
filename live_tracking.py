"""On-demand camera tracking sessions and MJPEG frame delivery."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from threading import Event, Lock, Thread

LOGGER = logging.getLogger("citypulse.tracking")


class TrackingSessionManager:
    def __init__(self, max_sessions: int = 3):
        self.max_sessions, self._sessions, self._lock = max_sessions, {}, Lock()
        self._model, self._model_lock = None, Lock()

    def _load_model(self):
        from tracking import MODEL_PATH
        from ultralytics import YOLO
        with self._model_lock:
            if self._model is None:
                if not MODEL_PATH.is_file():
                    raise RuntimeError("YOLO model file is unavailable")
                LOGGER.info("[YOLO] Loading shared model")
                self._model = YOLO(str(MODEL_PATH))
            return self._model

    def start(self, camera: dict) -> dict:
        camera_id = camera["id"]
        if not camera.get("tracking_available"):
            raise PermissionError(camera.get("source_error") or "No authorised live source is configured")
        with self._lock:
            current = self._sessions.get(camera_id)
            if current and current["status"] in {"Starting", "Running"}:
                return self._public(current)
            if sum(item["status"] in {"Starting", "Running"} for item in self._sessions.values()) >= self.max_sessions:
                raise RuntimeError(f"The prototype supports at most {self.max_sessions} active tracking sessions")
            session = {"camera_id": camera_id, "status": "Starting", "error": None, "stop": Event(), "original": None, "tracked": None, "started_at": datetime.now(timezone.utc).isoformat(), "last_frame_at": None, "frames_processed": 0, "vehicle_count": 0, "vehicles": [], "processing_fps": 0.0, "processing_latency_ms": None, "stream_type": camera["stream_type"], "source": camera["stream_source"]}
            self._sessions[camera_id] = session
        LOGGER.info("[CAMERA] Starting camera %s", camera_id)
        Thread(target=self._run, args=(session,), daemon=True, name=f"tracking-{camera_id}").start()
        return self._public(session)

    def stop(self, camera_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(camera_id)
            if not session:
                return False
            if session["status"] in {"Starting", "Running"}:
                session["status"] = "Stopping"
                session["stop"].set()
        return True

    def status(self, camera_id: str) -> dict:
        with self._lock:
            session = self._sessions.get(camera_id)
            return self._public(session) if session else {"camera_id": camera_id, "status": "standby", "vehicle_count": 0, "vehicles": [], "processing_fps": 0.0, "processing_latency_ms": None, "error": None}

    def frame(self, camera_id: str, view: str):
        key = "tracked" if view == "tracked" else "original"
        while True:
            with self._lock:
                session = self._sessions.get(camera_id)
                status, image = (session.get("status"), session.get(key)) if session else (None, None)
            if status not in {"Starting", "Running", "Stopping"}:
                return
            if image:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + image + b"\r\n"
            time.sleep(0.08)

    @staticmethod
    def _public(session: dict | None) -> dict:
        if not session:
            return {}
        keys = {"camera_id", "status", "error", "started_at", "last_frame_at", "frames_processed", "vehicle_count", "vehicles", "processing_fps", "processing_latency_ms", "stream_type"}
        return {key: session.get(key) for key in keys}

    def _run(self, session: dict) -> None:
        capture = None
        try:
            import cv2
            from tracking import frame_vehicle_metadata, tracking_class_ids
            LOGGER.info("[STREAM] Connecting to configured %s source", session["stream_type"])
            capture = cv2.VideoCapture(session["source"])
            if not capture.isOpened():
                raise RuntimeError("Could not open the configured media stream")
            model, started = self._load_model(), time.monotonic()
            session["status"] = "Running"
            while not session["stop"].is_set():
                ok, frame = capture.read()
                if not ok and session["stream_type"] == "mp4":
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0); ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Camera stream ended or became unavailable")
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]); session["original"] = encoded.tobytes() if ok else None
                began = time.monotonic()
                with self._model_lock:
                    result = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=tracking_class_ids(model), conf=0.25, verbose=False)[0]
                session["processing_latency_ms"] = round((time.monotonic() - began) * 1000, 1)
                session["vehicles"] = frame_vehicle_metadata(result); session["vehicle_count"] = len(session["vehicles"])
                ok, encoded = cv2.imencode(".jpg", result.plot(), [cv2.IMWRITE_JPEG_QUALITY, 80]); session["tracked"] = encoded.tobytes() if ok else None
                session["frames_processed"] += 1; session["last_frame_at"] = datetime.now(timezone.utc).isoformat(); session["processing_fps"] = round(session["frames_processed"] / max(time.monotonic() - started, 0.001), 1)
            session["status"] = "Stopped"; LOGGER.info("[TRACKING] Camera %s stopped", session["camera_id"])
        except Exception as exc:
            session["status"], session["error"] = "Error", str(exc); LOGGER.warning("[TRACKING] Camera %s failed: %s", session["camera_id"], exc)
        finally:
            if capture is not None:
                capture.release()


live_feed_manager = TrackingSessionManager()
