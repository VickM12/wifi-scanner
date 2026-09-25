import unittest

from app.motion import MotionDetector


class MotionDetectorTests(unittest.TestCase):
    def test_still_room_stays_low(self) -> None:
        det = MotionDetector()
        result = None
        for i in range(40):
            result = det.push_rssi(i * 0.15, -50.0 + ((i % 2) * 0.1), "aa:bb:cc:dd:ee:ff")
        assert result is not None
        self.assertLess(result.score, 0.2)
        self.assertEqual(result.state, "STILL")
        self.assertIsNotNone(result.rolling_mean)
        self.assertIsNotNone(result.z_score)

    def test_step_change_raises_score(self) -> None:
        det = MotionDetector()
        for i in range(30):
            det.push_rssi(i * 0.15, -50.0, "aa:bb:cc:dd:ee:01")
        late = det.push_rssi(30 * 0.15, -42.0, "aa:bb:cc:dd:ee:01")
        self.assertGreater(late.score, 0.35)
        self.assertGreater(abs(late.residual or 0), 2.0)

    def test_calibration_stores_by_bssid(self) -> None:
        det = MotionDetector()
        bssid = "aa:bb:cc:dd:ee:02"
        det.start_calibration(bssid)
        self.assertEqual(det.calibration_status(bssid)["state"], "calibrating")
        for i in range(20):
            det.push_rssi(i * 0.15, -55.0 + (i % 3) * 0.2, bssid)
        stored = det.stop_calibration()
        assert stored is not None
        self.assertEqual(stored.bssid, bssid)
        self.assertGreater(stored.samples, 10)
        self.assertAlmostEqual(stored.mean, -55.0, delta=1.0)
        self.assertGreater(stored.sigma, 0.0)
        status = det.calibration_status(bssid)
        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["samples"], stored.samples)
        det.reset_baseline(bssid)
        self.assertEqual(det.calibration_status(bssid)["state"], "idle")

    def test_debounce_holds_state(self) -> None:
        det = MotionDetector()
        det.config.hold_s = 0.5
        det.config.threshold = 0.3
        first = det._debounce(1.0, 0.9, 0.3)
        self.assertEqual(first, "MOTION")
        brief = det._debounce(1.2, 0.0, 0.3)
        self.assertEqual(brief, "MOTION")
        later = det._debounce(1.6, 0.0, 0.3)
        self.assertEqual(later, "STILL")


if __name__ == "__main__":
    unittest.main()
