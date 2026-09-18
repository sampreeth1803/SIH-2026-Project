"""Server-side TomTom Flow Segment integration with a short-lived cache."""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock, Thread

FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
CACHE_TTL_SECONDS = 60


def _load_dotenv() -> None:
    """Load local development secrets without requiring an extra dependency."""
    dotenv = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(dotenv):
        return
    with open(dotenv, encoding="utf-8") as dotenv_file:
        for line in dotenv_file:
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.strip().split("=", 1)
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def congestion_level(speed_ratio: float | None) -> str:
    if speed_ratio is None:
        return "Unavailable"
    if speed_ratio < 0.35:
        return "Severe"
    if speed_ratio < 0.55:
        return "Heavy"
    if speed_ratio < 0.75:
        return "Moderate"
    return "Low"


def _ssl_context():
    """Prefer the operating-system trust store (important on managed Windows networks)."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


class TomTomTrafficService:
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        _load_dotenv()
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, dict]] = {}
        self._lock = Lock()
        self._refreshing = False

    @property
    def configured(self) -> bool:
        return bool(os.getenv("TOMTOM_API_KEY"))

    def _unavailable(self, reason: str, *, cached: dict | None = None) -> dict:
        if cached:
            return cached | {"available": False, "stale": True, "error": reason}
        return {
            "provider": "TomTom Traffic Flow", "available": False, "stale": False,
            "error": reason, "current_speed_kph": None, "free_flow_speed_kph": None,
            "speed_ratio": None, "travel_time_seconds": None, "free_flow_travel_time_seconds": None,
            "delay_seconds": None, "confidence": None, "incidents": [], "incident_count": 0,
            "congestion_level": "Unavailable", "heat_intensity": 0, "updated_at": None,
        }

    def camera_traffic(self, camera: dict) -> dict:
        camera_id = str(camera["id"])
        now = time.monotonic()
        with self._lock:
            cached_pair = self._cache.get(camera_id)
        cached = cached_pair[1] if cached_pair else None
        if cached_pair and now - cached_pair[0] < self.ttl_seconds:
            return cached | {"cached": True, "stale": False}
        if not self.configured:
            return self._unavailable("TOMTOM_API_KEY is not configured", cached=cached)
        latitude, longitude = camera.get("latitude"), camera.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)) or (latitude == 0 and longitude == 0) or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return self._unavailable("Camera has invalid coordinates", cached=cached)
        try:
            query = urllib.parse.urlencode({"key": os.environ["TOMTOM_API_KEY"], "point": f"{latitude},{longitude}", "unit": "KMPH"})
            request = urllib.request.Request(f"{FLOW_URL}?{query}", headers={"User-Agent": "CityPulse-AI/1.0"})
            with urllib.request.urlopen(request, timeout=8, context=_ssl_context()) as response:  # nosec B310: fixed HTTPS host
                payload = json.loads(response.read().decode("utf-8"))
            flow = payload["flowSegmentData"]
            current_speed = float(flow.get("currentSpeed", 0) or 0)
            free_flow_speed = float(flow.get("freeFlowSpeed", 0) or 0)
            speed_ratio = round(current_speed / free_flow_speed, 3) if free_flow_speed > 0 else None
            current_time = float(flow.get("currentTravelTime", 0) or 0)
            free_time = float(flow.get("freeFlowTravelTime", 0) or 0)
            result = {
                "provider": "TomTom Traffic Flow", "available": True, "cached": False, "stale": False,
                "error": None, "current_speed_kph": current_speed, "free_flow_speed_kph": free_flow_speed,
                "speed_ratio": speed_ratio, "travel_time_seconds": current_time,
                "free_flow_travel_time_seconds": free_time, "delay_seconds": max(0, round(current_time - free_time, 1)),
                "confidence": flow.get("confidence"), "incidents": [], "incident_count": 0,
                "congestion_level": congestion_level(speed_ratio), "heat_intensity": round(max(0, min(1, 1 - (speed_ratio or 1))), 3),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            with self._lock:
                self._cache[camera_id] = (now, result)
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
            return self._unavailable(f"TomTom traffic request failed: {exc}", cached=cached)

    def all_camera_traffic(self, cameras: list[dict]) -> list[dict]:
        # A bounded pool keeps a full node refresh responsive without flooding the provider.
        with ThreadPoolExecutor(max_workers=8) as executor:
            return list(executor.map(self.camera_traffic, cameras))

    def cached_camera_traffic(self, camera: dict) -> dict:
        with self._lock:
            cached_pair = self._cache.get(str(camera["id"]))
        if cached_pair:
            return cached_pair[1] | {"cached": True, "stale": time.monotonic() - cached_pair[0] >= self.ttl_seconds}
        return self._unavailable("TomTom refresh pending")

    def refresh_all_async(self, cameras: list[dict]) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True

        def refresh() -> None:
            try:
                self.all_camera_traffic(cameras)
            finally:
                with self._lock:
                    self._refreshing = False

        Thread(target=refresh, daemon=True).start()


tomtom_traffic = TomTomTrafficService()
