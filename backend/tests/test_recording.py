import json
import tempfile
import unittest
from pathlib import Path

from app.recording import ExperimentRecorder, RECORD_FIELDS, serialize_record


class RecordingTests(unittest.TestCase):
    def test_serialize_record_field_order(self) -> None:
        row = serialize_record(
            {
                "timestamp": 100.5,
                "ssid": "Home",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "channel": 6,
                "band": "2.4",
                "rssi": -50.0,
                "rolling_mean": -51.0,
                "rolling_std": 0.8,
                "residual": 1.0,
                "z_score": 1.25,
                "motion_score": 0.2,
                "label": "walking",
                "extra": "ignored",
            }
        )
        self.assertEqual(list(row.keys()), RECORD_FIELDS)
        self.assertEqual(row["label"], "walking")
        self.assertNotIn("extra", row)

    def test_csv_and_jsonl_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rec = ExperimentRecorder(Path(tmp))
            path = rec.start("walking", "csv", 1_700_000_000.0)
            rec.append(
                {
                    "timestamp": 1_700_000_000.5,
                    "ssid": "Home",
                    "bssid": "aa:bb:cc:dd:ee:ff",
                    "channel": 36,
                    "band": "5",
                    "rssi": -48.0,
                    "rolling_mean": -50.0,
                    "rolling_std": 1.0,
                    "residual": 2.0,
                    "z_score": 2.0,
                    "motion_score": 0.4,
                    "label": "walking",
                }
            )
            rec.stop()
            text = path.read_text(encoding="utf-8")
            self.assertIn("timestamp,ssid,bssid", text)
            self.assertIn("walking", text)

            rec.start("sitting", "jsonl", 1_700_000_010.0)
            rec.append(
                {
                    "timestamp": 1_700_000_011.0,
                    "ssid": "Home",
                    "bssid": "aa:bb:cc:dd:ee:ff",
                    "channel": 36,
                    "band": "5",
                    "rssi": -49.0,
                    "rolling_mean": -50.0,
                    "rolling_std": 0.5,
                    "residual": 1.0,
                    "z_score": 2.0,
                    "motion_score": 0.15,
                    "label": "sitting",
                }
            )
            jsonl_path = rec.path
            rec.stop()
            assert jsonl_path is not None
            payload = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["label"], "sitting")
            self.assertEqual(payload["bssid"], "aa:bb:cc:dd:ee:ff")


if __name__ == "__main__":
    unittest.main()
