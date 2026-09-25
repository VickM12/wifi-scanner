"""Print duration and RSSI range for every file in ../recordings."""

import csv
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "recordings"
for path in sorted(root.glob("*.csv")):
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        print(f"{path.name}  empty")
        continue
    rssi = [float(r["rssi"]) for r in rows]
    t0 = float(rows[0]["timestamp"])
    t1 = float(rows[-1]["timestamp"])
    unique = sorted(set(rssi))
    print(
        f"{path.name}  {t1 - t0:.1f}s  first={rssi[0]:.0f} last={rssi[-1]:.0f}  values={unique}"
    )
