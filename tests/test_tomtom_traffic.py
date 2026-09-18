import os
import unittest
from unittest.mock import patch

from tomtom_traffic import TomTomTrafficService, congestion_level


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TomTomTrafficTests(unittest.TestCase):
    def test_congestion_thresholds(self):
        self.assertEqual(congestion_level(0.2), "Severe")
        self.assertEqual(congestion_level(0.4), "Heavy")
        self.assertEqual(congestion_level(0.6), "Moderate")
        self.assertEqual(congestion_level(0.8), "Low")

    @patch.dict(os.environ, {"TOMTOM_API_KEY": "test-key"})
    @patch("tomtom_traffic.urllib.request.urlopen")
    def test_flow_response_becomes_heatmap_data(self, urlopen):
        urlopen.return_value = _Response(b'{"flowSegmentData":{"currentSpeed":20,"freeFlowSpeed":50,"currentTravelTime":90,"freeFlowTravelTime":60,"confidence":0.91}}')
        traffic = TomTomTrafficService().camera_traffic({"id": "CAM-1", "latitude": 12.97, "longitude": 77.59})
        self.assertTrue(traffic["available"])
        self.assertEqual(traffic["congestion_level"], "Heavy")
        self.assertEqual(traffic["heat_intensity"], 0.6)
        self.assertEqual(traffic["delay_seconds"], 30)

    @patch.dict(os.environ, {"TOMTOM_API_KEY": "test-key"})
    def test_missing_coordinates_never_call_tomtom(self):
        traffic = TomTomTrafficService().camera_traffic({"id": "CAM-1", "latitude": 0, "longitude": 0})
        self.assertFalse(traffic["available"])
        self.assertIn("invalid coordinates", traffic["error"])


if __name__ == "__main__":
    unittest.main()
