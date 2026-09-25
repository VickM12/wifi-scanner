import math
import unittest

from app.stats import motion_score, residual, rolling_mean, rolling_std, rolling_variance, z_score


class RollingStatsTests(unittest.TestCase):
    def test_rolling_mean(self) -> None:
        self.assertEqual(rolling_mean([]), 0.0)
        self.assertAlmostEqual(rolling_mean([-50.0, -52.0, -48.0]), -50.0)

    def test_rolling_variance_and_std(self) -> None:
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        self.assertAlmostEqual(rolling_variance(values), 4.571428571428571, places=6)
        self.assertAlmostEqual(rolling_std(values), math.sqrt(4.571428571428571), places=6)
        self.assertEqual(rolling_variance([3.0]), 0.0)
        self.assertEqual(rolling_std([]), 0.0)

    def test_residual(self) -> None:
        self.assertAlmostEqual(residual(-46.0, -50.0), 4.0)

    def test_z_score_uses_noise_floor(self) -> None:
        self.assertAlmostEqual(z_score(2.0, 0.0, 0.5), 4.0)
        self.assertAlmostEqual(z_score(-3.0, 1.5, 0.4), -2.0)

    def test_motion_score_normalized(self) -> None:
        still = motion_score(0.2, 0.1, 0.8, 0.4)
        moving = motion_score(4.0, 3.0, 0.8, 0.4)
        self.assertGreaterEqual(still, 0.0)
        self.assertLess(still, 0.25)
        self.assertGreater(moving, 0.7)
        self.assertLessEqual(moving, 1.0)
        self.assertEqual(motion_score(100.0, 100.0, 0.1, 0.4), 1.0)


if __name__ == "__main__":
    unittest.main()
