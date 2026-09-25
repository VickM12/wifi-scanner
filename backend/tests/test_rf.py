import unittest

from app.rf import bssid_angle, format_mac


class BssidAngleTests(unittest.TestCase):
    def test_deterministic(self) -> None:
        a = bssid_angle("AA:BB:CC:DD:EE:FF")
        b = bssid_angle("aa:bb:cc:dd:ee:ff")
        c = bssid_angle("aa-bb-cc-dd-ee-ff")
        self.assertEqual(format_mac("AA:BB:CC:DD:EE:FF"), "aa:bb:cc:dd:ee:ff")
        self.assertAlmostEqual(a, b)
        self.assertAlmostEqual(a, c)
        self.assertGreaterEqual(a, 0.0)
        self.assertLess(a, 6.28318530718)

    def test_different_bssids_usually_differ(self) -> None:
        a = bssid_angle("aa:bb:cc:dd:ee:01")
        b = bssid_angle("aa:bb:cc:dd:ee:02")
        self.assertNotAlmostEqual(a, b)


if __name__ == "__main__":
    unittest.main()
