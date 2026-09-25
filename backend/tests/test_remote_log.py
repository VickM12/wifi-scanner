import json
import tempfile
import unittest
from pathlib import Path

from app.remote_log import RemoteNodeLog, row_from_report, safe_node_id


class RemoteLogTests(unittest.TestCase):
    def test_safe_node_id(self) -> None:
        self.assertEqual(safe_node_id("fedora"), "fedora")
        self.assertEqual(safe_node_id("../weird name"), "weird_name")

    def test_row_and_append(self) -> None:
        report = {
            "id": "fedora",
            "t": 100.5,
            "link": {"ssid": "ExampleNet", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -62, "channel": 48, "band": "5"},
            "motion": {"score": 0.4, "state": "MOTION", "rolling_mean": -60, "rolling_std": 1.0, "residual": -2, "z_score": -2},
            "aps": [{"ssid": "ExampleNet", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -62, "channel": 48, "band": "5", "linked": True}],
            "position": None,
        }
        row = row_from_report(report, 101.0)
        self.assertEqual(row["node_id"], "fedora")
        self.assertEqual(row["rssi"], -62)
        self.assertEqual(row["motion_score"], 0.4)
        with tempfile.TemporaryDirectory() as tmp:
            log = RemoteNodeLog(Path(tmp))
            path = log.append(report, 1_700_000_000.0)
            self.assertTrue(path.is_file())
            payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["node_id"], "fedora")
            self.assertEqual(log.status()["nodes"][0]["samples"], 1)


if __name__ == "__main__":
    unittest.main()
