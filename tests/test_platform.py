import tempfile
import unittest
from pathlib import Path

from privacy import anonymize_plate, normalize_plate, redact_plate_results
from storage import AnalyticsStore
from vehicle_classes import VEHICLE_TAXONOMY, model_class_name, model_vehicle_class_ids


class PlatformTests(unittest.TestCase):
    def test_taxonomy_has_fourteen_classes(self):
        self.assertEqual(len(VEHICLE_TAXONOMY), 14)
        names = {item["name"] for item in VEHICLE_TAXONOMY}
        self.assertIn("two-wheeler", names)
        self.assertIn("tempo-traveller", names)

    def test_custom_model_labels_are_normalized(self):
        names = {0: "sedan", 1: "motorcycle", 2: "bus"}
        self.assertEqual(model_vehicle_class_ids(names), [0, 1, 2])
        self.assertEqual(model_class_name(names, 1), "two-wheeler")

    def test_plate_privacy_is_stable_and_non_reversible(self):
        self.assertEqual(normalize_plate("KA 01 AB-1234"), "KA01AB1234")
        self.assertEqual(anonymize_plate("KA 01 AB-1234", "test"), anonymize_plate("KA01AB1234", "test"))
        result = redact_plate_results([[None, "KA 01 AB-1234", 0.987]], "test")
        self.assertNotIn("KA01AB1234", str(result))
        self.assertEqual(result[0]["confidence"], 0.987)

    def test_analytics_store_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AnalyticsStore(Path(directory) / "analytics.db")
            store.record(
                "CAM-BLR-01",
                {
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "average_occupancy": 0.2,
                    "peak_occupancy": 0.4,
                    "peak_vehicles_in_frame": 7,
                    "vehicle_counts": {"sedan": 3},
                },
                "Heavy",
            )
            history = store.history("CAM-BLR-01")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["vehicle_counts"], {"sedan": 3})
            self.assertEqual(history[0]["traffic_status"], "Heavy")


if __name__ == "__main__":
    unittest.main()
