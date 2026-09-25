from app.collectors.demo import DemoCollector
from app.collectors.esp32_csi import parse_csi_datagram
from app.motion import MotionDetector
from app.rf import bssid_angle, freq_mhz_to_channel, normalize_rssi

motion = MotionDetector()
result = None
for i in range(20):
    result = motion.push_rssi(i * 0.1, -50 + ((i % 3) - 1) * 3, "aa:bb:cc:dd:ee:ff")
assert result is not None
frame = parse_csi_datagram(
    b'{"v":1,"seq":1,"rssi":-40,"mac":"aa:bb:cc:dd:ee:ff","noise":-90,"amps":[1,2,3]}'
)
demo = DemoCollector()
assert frame is not None
print(
    "motion",
    round(result.score, 3),
    "state",
    result.state,
    "csi",
    frame.seq,
    "aps",
    len(demo.scan_aps()),
    "rssi",
    normalize_rssi(70),
    "ch",
    freq_mhz_to_channel(2437),
    "angle",
    round(bssid_angle("aa:bb:cc:dd:ee:ff"), 4),
)
