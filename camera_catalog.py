"""OpenCity Bengaluru CCTV location catalogue import and resilient cache."""
from __future__ import annotations
import json, re, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "data" / "bengaluru_camera_catalogue.json"
RESOURCE_ID = "64a4e7d1-701d-4983-a487-283d62bc514b"
CKAN_RESOURCE_API = f"https://data.opencity.in/api/3/action/resource_show?id={RESOURCE_ID}"
ATTRIBUTION, LICENCE = "OpenCity / Thejesh GN and OpenStreetMap", "CC BY-NC-SA 4.0"

def _request(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "CityPulse-AI/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:  # nosec B310 - fixed HTTPS source
        return response.read()

def _source_kml() -> bytes:
    metadata = json.loads(_request(CKAN_RESOURCE_API).decode("utf-8"))
    url = metadata.get("result", {}).get("url") if metadata.get("success") else None
    if not url: raise RuntimeError("OpenCity resource metadata did not include a KML URL")
    return _request(url)

def _plain_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()

def parse_kml(kml: bytes) -> list[dict]:
    root, ns, cameras = ET.fromstring(kml), {"k": "http://www.opengis.net/kml/2.2"}, []
    for index, placemark in enumerate(root.findall(".//k:Placemark", ns), start=1):
        coordinates = placemark.findtext(".//k:Point/k:coordinates", namespaces=ns)
        if not coordinates: continue
        try: longitude, latitude, *_ = [float(item) for item in coordinates.strip().split(",")]
        except ValueError: continue
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90): continue
        name = _plain_text(placemark.findtext("k:name", namespaces=ns)) or f"Bengaluru CCTV node {index}"
        description = _plain_text(placemark.findtext("k:description", namespaces=ns))
        cameras.append({"id": f"CAT-BLR-{index:04d}", "name": name, "location": description or "Bengaluru", "latitude": latitude, "longitude": longitude, "metadata": "OpenCity camera location catalogue", "source_type": "catalogue", "source_attribution": ATTRIBUTION, "source_licence": LICENCE, "video_available": False})
    return cameras

def spatial_sample(cameras: list[dict], count: int = 100) -> list[dict]:
    if len(cameras) <= count: return sorted(cameras, key=lambda item: item["id"])
    min_lat, max_lat = min(item["latitude"] for item in cameras), max(item["latitude"] for item in cameras)
    min_lon, max_lon = min(item["longitude"] for item in cameras), max(item["longitude"] for item in cameras)
    grid: dict[tuple[int, int], list[dict]] = {}
    for camera in cameras:
        row = min(9, int((camera["latitude"] - min_lat) / max(max_lat - min_lat, .000001) * 10))
        column = min(9, int((camera["longitude"] - min_lon) / max(max_lon - min_lon, .000001) * 10))
        grid.setdefault((row, column), []).append(camera)
    selected = [sorted(items, key=lambda item: item["id"])[0] for _, items in sorted(grid.items())]
    remaining = [item for item in sorted(cameras, key=lambda item: item["id"]) if item not in selected]
    return (selected + remaining[:max(0, count - len(selected))])[:count]

def load_catalogue(refresh: bool = True, count: int = 100) -> list[dict]:
    if refresh:
        try:
            cameras = spatial_sample(parse_kml(_source_kml()), count)
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(cameras, indent=2), encoding="utf-8")
            return cameras
        except (OSError, ValueError, ET.ParseError, json.JSONDecodeError, RuntimeError): pass
    if CACHE_PATH.is_file():
        try: return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): pass
    return []
