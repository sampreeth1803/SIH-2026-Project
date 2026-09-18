"""Optional real-model demo verification; enable explicitly on a capable machine."""
import os
import time
import unittest

from api import camera_registry
from live_tracking import TrackingSessionManager


@unittest.skipUnless(os.getenv("CITYPULSE_RUN_MODEL_TESTS") == "1", "Set CITYPULSE_RUN_MODEL_TESTS=1 to run YOLO MP4 integration")
class TrackingEndToEndTests(unittest.TestCase):
    def test_local_mp4_produces_annotated_frame_and_metadata(self):
        camera = camera_registry.get_camera("DEMO-BLR-LOCAL")
        manager = TrackingSessionManager(max_sessions=1)
        manager.start(camera)
        deadline = time.monotonic() + 90
        status = manager.status(camera["id"])
        while time.monotonic() < deadline and status["status"] in {"Starting", "Running"} and not status["frames_processed"]:
            time.sleep(0.25)
            status = manager.status(camera["id"])
        manager.stop(camera["id"])
        self.assertEqual(status["status"], "Running", status.get("error"))
        self.assertGreater(status["frames_processed"], 0)
        self.assertIsInstance(status["vehicles"], list)


if __name__ == "__main__":
    unittest.main()
