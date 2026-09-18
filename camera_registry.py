"""Authorised camera configuration and source validation for CityPulse."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse


SUPPORTED_STREAM_TYPES = {"none", "mp4", "mjpeg", "hls", "rtsp"}


class CameraRegistry:
    """Combines local demos, configured feeds, and location-only catalogue nodes.

    `stream_source` is internal-only and is deliberately omitted from public API
    responses so RTSP credentials and private URLs cannot reach the browser.
    """

    def __init__(self, base_dir: Path, demo_cameras: list[dict], config_name: str = "live_feeds.json"):
        self.base_dir = base_dir.resolve()
        self.demo_cameras = demo_cameras
        self.config_path = self.base_dir / config_name

    def _configured_feeds(self) -> list[dict]:
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            return list(payload.values()) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _resolve_source(self, item: dict) -> tuple[str | None, str | None]:
        source_type = str(item.get("stream_type") or "").lower()
        source = item.get("source_url") or item.get("stream_url")
        source_env = item.get("source_env")
        if source_env:
            if not isinstance(source_env, str) or not source_env.startswith("CAMERA_"):
                return None, "source_env must name a CAMERA_* environment variable"
            source = os.getenv(source_env)
        if not source_type:
            source_type = "mp4" if source and str(source).lower().endswith(".mp4") else "none"
        if source_type not in SUPPORTED_STREAM_TYPES:
            return None, f"Unsupported stream_type: {source_type}"
        if source_type == "none":
            return None, None
        if not isinstance(source, str) or not source.strip():
            return None, "No authorised source is configured"
        source = source.strip()
        if source_type == "mp4":
            path = (self.base_dir / source).resolve() if not Path(source).is_absolute() else Path(source).resolve()
            if self.base_dir not in path.parents or not path.is_file():
                return None, "Configured MP4 source is unavailable"
            return str(path), None
        parsed = urlparse(source)
        allowed = {"mjpeg": {"http", "https"}, "hls": {"http", "https"}, "rtsp": {"rtsp", "rtsps"}}[source_type]
        if parsed.scheme not in allowed or not parsed.netloc:
            return None, f"Invalid {source_type.upper()} source URL"
        if parsed.username or parsed.password:
            return None, "Credentials must be supplied through source_env, not a committed URL"
        return source, None

    def _normalise(self, item: dict, *, source_kind: str) -> dict:
        camera = dict(item)
        camera_id = str(camera.get("camera_id") or camera.get("id") or "").strip()
        camera["id"] = camera_id
        camera["camera_id"] = camera_id
        camera["source_type"] = source_kind
        camera["enabled"] = bool(camera.get("enabled", source_kind == "demo"))
        stream_type = str(camera.get("stream_type") or ("mp4" if source_kind == "demo" else "none")).lower()
        camera["stream_type"] = stream_type
        source, error = self._resolve_source(camera)
        if source_kind == "catalogue":
            source, error, camera["enabled"], camera["stream_type"] = None, None, False, "none"
        camera["stream_source"] = source
        camera["source_error"] = error
        camera["source_available"] = bool(camera["enabled"] and source and not error)
        camera["tracking_available"] = camera["source_available"]
        return camera

    def all_cameras(self, catalogue_cameras: list[dict] | None = None) -> list[dict]:
        cameras: list[dict] = []
        seen: set[str] = set()
        for item in self.demo_cameras:
            camera = self._normalise(item | {"source_url": str(item.get("video_path", "")), "stream_type": "mp4", "enabled": True}, source_kind="demo")
            if camera["id"]:
                cameras.append(camera); seen.add(camera["id"])
        for item in self._configured_feeds():
            camera = self._normalise(item, source_kind="configured")
            if camera["id"] and camera["id"] not in seen:
                cameras.append(camera); seen.add(camera["id"])
        for item in catalogue_cameras or []:
            camera = self._normalise(item, source_kind="catalogue")
            if camera["id"] and camera["id"] not in seen:
                cameras.append(camera); seen.add(camera["id"])
        return cameras

    def get_camera(self, camera_id: str, catalogue_cameras: list[dict] | None = None) -> dict | None:
        return next((item for item in self.all_cameras(catalogue_cameras) if item["id"] == camera_id), None)

    @staticmethod
    def public(camera: dict) -> dict:
        hidden = {"stream_source", "source_url", "stream_url", "source_env", "video_path"}
        return {key: value for key, value in camera.items() if key not in hidden}
