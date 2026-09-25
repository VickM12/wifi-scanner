import unittest

from app.nodes import NodeRegistry, build_node_report, compact_aps


class NodeReportTests(unittest.TestCase):
    def test_compact_aps_limits_and_fields(self) -> None:
        aps = [{"ssid": f"n{i}", "bssid": f"aa:bb:cc:dd:ee:{i:02x}", "rssi": -50, "channel": 6, "band": "2.4", "linked": i == 0, "extra": 1} for i in range(40)]
        out = compact_aps(aps)
        self.assertEqual(len(out), 24)
        self.assertEqual(out[0]["linked"], True)
        self.assertNotIn("extra", out[0])

    def test_build_and_ingest(self) -> None:
        report = build_node_report(
            node_id="laptop",
            t=100.0,
            link={"ssid": "ExampleNet", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -60},
            motion={"score": 0.4, "state": "MOTION", "rssi": -60, "z_score": 2.0},
            aps=[{"ssid": "ExampleNet", "bssid": "aa:bb:cc:dd:ee:ff", "rssi": -60, "channel": 48, "band": "5", "linked": True}],
            position={"room": "kitchen", "x": None, "y": None, "z": None},
        )
        self.assertEqual(report["id"], "laptop")
        self.assertEqual(report["position"]["room"], "kitchen")
        registry = NodeRegistry(ttl_s=1.0)
        stored = registry.ingest(report, now=100.0)
        self.assertEqual(stored["id"], "laptop")
        self.assertEqual(len(registry.remote_list(now=100.1)), 1)
        self.assertEqual(len(registry.remote_list(now=102.0)), 0)


if __name__ == "__main__":
    unittest.main()
