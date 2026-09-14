import unittest

from api import CAMERAS, estimate_camera_congestion, predict_route


class RoutePredictorTests(unittest.TestCase):
    def test_time_of_day_affects_congestion_prediction(self):
        camera = CAMERAS[0]
        morning = estimate_camera_congestion(camera, "08:30")
        night = estimate_camera_congestion(camera, "23:00")
        self.assertGreaterEqual(morning, night)
        self.assertGreaterEqual(morning, 0.0)
        self.assertLessEqual(morning, 1.0)
        self.assertGreaterEqual(night, 0.0)
        self.assertLessEqual(night, 1.0)

    def test_predict_route_returns_a_valid_path(self):
        route = predict_route("CAM-BLR-01", "CAM-BLR-04", "18:45")
        self.assertEqual(route["from"], "CAM-BLR-01")
        self.assertEqual(route["to"], "CAM-BLR-04")
        self.assertGreaterEqual(len(route["route"]), 2)
        self.assertGreater(route["estimated_travel_minutes"], 0)
        self.assertGreaterEqual(route["average_congestion"], 0)
        self.assertLess(route["estimated_travel_minutes"], 20)

    def test_same_camera_route_has_no_artificial_minimum_delay(self):
        route = predict_route("CAM-BLR-01", "CAM-BLR-01", "12:00")
        self.assertEqual(route["route"], ["CAM-BLR-01"])
        self.assertEqual(route["estimated_travel_minutes"], 1.0)


if __name__ == "__main__":
    unittest.main()
