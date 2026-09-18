import unittest

from fastapi.testclient import TestClient
from api import app


class TrackingApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_demo_camera_is_safe_to_expose(self):
        camera = self.client.get("/api/cameras/DEMO-BLR-LOCAL")
        self.assertEqual(camera.status_code, 200)
        self.assertTrue(camera.json()["tracking_available"])
        self.assertNotIn("source_url", camera.json())

    def test_unknown_camera_returns_404(self):
        self.assertEqual(self.client.get("/api/cameras/no-such-camera/tracking").status_code, 404)

    def test_unconfigured_camera_cannot_start(self):
        response = self.client.post("/api/cameras/OPENCCTV-14534/tracking/start")
        self.assertEqual(response.status_code, 403)

    def test_stream_endpoint_has_mjpeg_type(self):
        response = self.client.get("/api/cameras/DEMO-BLR-LOCAL/stream")
        self.assertEqual(response.status_code, 200)
        self.assertIn("multipart/x-mixed-replace", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
