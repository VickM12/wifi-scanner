import unittest

from app.rf import radar_offset, relative_bearing_deg, wrap_deg


class HeadingTests(unittest.TestCase):
    def test_behind_when_facing_opposite(self) -> None:
        # Deco at southwest (225), face northeast (45) => behind.
        rel = relative_bearing_deg(225.0, 45.0)
        self.assertAlmostEqual(rel, 180.0, places=5)
        x, y = radar_offset(rel, 10.0)
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertGreater(y, 9.0)

    def test_ahead_when_facing_the_ap(self) -> None:
        rel = relative_bearing_deg(45.0, 45.0)
        self.assertAlmostEqual(rel, 0.0, places=5)
        x, y = radar_offset(rel, 10.0)
        self.assertAlmostEqual(x, 0.0, places=5)
        self.assertLess(y, -9.0)

    def test_wrap(self) -> None:
        self.assertAlmostEqual(wrap_deg(-10), 350.0)
        self.assertAlmostEqual(relative_bearing_deg(10.0, 350.0), 20.0, places=5)


if __name__ == "__main__":
    unittest.main()
