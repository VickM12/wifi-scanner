import unittest

from app.geometry import estimate_fix, house_configured, normalize_house
from app.rf import rssi_to_meters


HOUSE = {
    "floors": [
        {"id": "1", "name": "living", "z": 0, "w": 12, "d": 8},
        {"id": "2", "name": "bedroom", "z": 3, "w": 12, "d": 8},
        {"id": "3", "name": "office", "z": 6, "w": 12, "d": 8},
    ],
    "anchors": [
        {
            "id": "deco-br",
            "label": "bedroom Deco",
            "floor": "2",
            "x": 9,
            "y": 2,
            "bssids": ["aa:bb:cc:dd:ee:15", "aa:bb:cc:dd:ee:14"],
        },
        {
            "id": "deco-lr",
            "label": "living Deco",
            "floor": "1",
            "x": 2,
            "y": 6,
            "bssids": ["aa:bb:cc:dd:ee:45", "aa:bb:cc:dd:ee:44"],
        },
    ],
}


class GeometryTests(unittest.TestCase):
    def test_default_rooms_are_partial_stack(self) -> None:
        house = normalize_house({})
        living = next(r for r in house["rooms"] if r["id"] == "living")
        bedroom = next(r for r in house["rooms"] if r["id"] == "bedroom")
        office = next(r for r in house["rooms"] if r["id"] == "office")
        self.assertAlmostEqual(living["w"], house["footprint"]["w"] / 2.0)
        self.assertLess(bedroom["w"], house["footprint"]["w"])
        self.assertLess(office["w"], bedroom["w"] + 0.1)
        self.assertEqual(living["x"], bedroom["x"])

    def test_missing_house_is_none(self) -> None:
        self.assertIsNone(estimate_fix(None, [], None))
        self.assertFalse(house_configured(normalize_house({})))
        empty = normalize_house({"floors": HOUSE["floors"], "anchors": []})
        self.assertFalse(house_configured({"floors": empty["floors"], "anchors": [
            {**empty["anchors"][0], "bssids": []} if empty["anchors"] else {"bssids": []}
        ]}))
        self.assertIsNone(estimate_fix({"floors": HOUSE["floors"], "anchors": [
            {**HOUSE["anchors"][0], "bssids": []},
            {**HOUSE["anchors"][1], "bssids": []},
        ]}, [{"bssid": "aa:bb:cc:dd:ee:15", "rssi": -35, "band": "5"}], None))

    def test_under_node_small_ring_on_bedroom_floor(self) -> None:
        near = rssi_to_meters(-35, tx_power_dbm=-35.0, path_loss_n=3.0)
        self.assertLess(near, 1.2)
        fix = estimate_fix(
            HOUSE,
            [
                {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -35, "band": "5", "linked": True},
                {"bssid": "aa:bb:cc:dd:ee:45", "rssi": -70, "band": "5", "linked": False},
            ],
            {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -35, "band": "5"},
        )
        self.assertIsNotNone(fix)
        assert fix is not None
        bedroom_rings = [r for r in fix["rings"] if r["anchor_id"] == "deco-br" and r["floor"] == "2"]
        self.assertTrue(bedroom_rings)
        self.assertLess(bedroom_rings[0]["r_outer"], 4.0)
        self.assertEqual(fix["floor"], "2")
        self.assertLess(abs(fix["x"] - 9.0), 3.5)
        self.assertLess(abs(fix["y"] - 2.0), 3.5)

    def test_far_second_anchor_still_intersects(self) -> None:
        fix = estimate_fix(
            HOUSE,
            [
                {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -35, "band": "5", "linked": True},
                {"bssid": "aa:bb:cc:dd:ee:45", "rssi": -72, "band": "5", "linked": False},
            ],
            {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -35, "band": "5"},
        )
        self.assertIsNotNone(fix)
        assert fix is not None
        self.assertGreaterEqual(len(fix["candidates"]), 1)
        self.assertGreaterEqual(len(fix["rings"]), 2)

    def test_strong_living_anchor_prefers_living_floor(self) -> None:
        fix = estimate_fix(
            HOUSE,
            [
                {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -68, "band": "5", "linked": True},
                {"bssid": "aa:bb:cc:dd:ee:45", "rssi": -38, "band": "5", "linked": False},
            ],
            {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -68, "band": "5"},
        )
        self.assertIsNotNone(fix)
        assert fix is not None
        self.assertEqual(fix["floor"], "1")
        self.assertEqual(fix["room"], "living")

    def test_groups_24_and_5_as_one_anchor(self) -> None:
        fix = estimate_fix(
            HOUSE,
            [
                {"bssid": "aa:bb:cc:dd:ee:14", "rssi": -40, "band": "2.4", "linked": False},
                {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -36, "band": "5", "linked": True},
                {"bssid": "aa:bb:cc:dd:ee:45", "rssi": -70, "band": "5", "linked": False},
            ],
            {"bssid": "aa:bb:cc:dd:ee:15", "rssi": -36, "band": "5"},
        )
        self.assertIsNotNone(fix)
        assert fix is not None
        ids = [a["id"] for a in fix["anchors"]]
        self.assertEqual(ids.count("deco-br"), 1)
        br = next(a for a in fix["anchors"] if a["id"] == "deco-br")
        self.assertEqual(br["rssi"], -36)
        self.assertEqual(br["band"], "5")


if __name__ == "__main__":
    unittest.main()
