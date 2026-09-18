import json
import os
import tempfile
import unittest
from pathlib import Path

from camera_registry import CameraRegistry


class CameraRegistryTests(unittest.TestCase):
    def _registry(self, payload):
        directory = tempfile.TemporaryDirectory()
        base = Path(directory.name)
        (base / "videos").mkdir()
        (base / "videos" / "demo.mp4").write_bytes(b"demo")
        (base / "live_feeds.json").write_text(json.dumps(payload), encoding="utf-8")
        self.addCleanup(directory.cleanup)
        return CameraRegistry(base, [{"id": "DEMO", "video_path": base / "videos" / "demo.mp4"}])

    def test_mp4_and_catalogue_sources_are_distinct(self):
        registry = self._registry([{"id": "REMOTE", "stream_type": "none", "enabled": False}])
        cameras = registry.all_cameras([{"id": "CAT", "latitude": 12.9, "longitude": 77.5}])
        self.assertTrue(next(item for item in cameras if item["id"] == "DEMO")["tracking_available"])
        self.assertFalse(next(item for item in cameras if item["id"] == "CAT")["tracking_available"])

    def test_private_source_comes_only_from_environment(self):
        os.environ["CAMERA_TEST_URL"] = "rtsp://example.test/live"
        self.addCleanup(os.environ.pop, "CAMERA_TEST_URL", None)
        registry = self._registry([{"id": "RTSP", "stream_type": "rtsp", "source_env": "CAMERA_TEST_URL", "enabled": True}])
        camera = registry.get_camera("RTSP")
        self.assertTrue(camera["source_available"])
        self.assertNotIn("stream_source", registry.public(camera))

    def test_invalid_source_is_not_trackable(self):
        registry = self._registry([{"id": "BAD", "stream_type": "hls", "source_url": "file:///bad.m3u8", "enabled": True}])
        self.assertFalse(registry.get_camera("BAD")["tracking_available"])


if __name__ == "__main__":
    unittest.main()
