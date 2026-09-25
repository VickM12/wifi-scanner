import csv
import statistics
from pathlib import Path


def summarize(path: Path) -> None:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            try:
                rows.append(
                    {
                        "rssi": float(raw["rssi"]),
                        "z": abs(float(raw["z_score"] or 0)),
                        "s": float(raw["motion_score"] or 0),
                    }
                )
            except ValueError:
                continue
    if not rows:
        print(f"{path.name}: empty")
        return
    rssi = [r["rssi"] for r in rows]
    zvals = [r["z"] for r in rows]
    scores = [r["s"] for r in rows]
    zvals_sorted = sorted(zvals)
    scores_sorted = sorted(scores)
    p95z = zvals_sorted[max(0, int(0.95 * len(zvals_sorted)) - 1)]
    p95s = scores_sorted[max(0, int(0.95 * len(scores_sorted)) - 1)]
    print(path.name)
    print(
        f"  n={len(rows)}  rssi {min(rssi):.1f}..{max(rssi):.1f}  "
        f"mean={statistics.mean(rssi):.2f}  std={statistics.pstdev(rssi):.2f}"
    )
    print(
        f"  |z| max={max(zvals):.2f} p95={p95z:.2f}  "
        f"score max={max(scores):.2f} p95={p95s:.2f}  "
        f"score>=0.35={sum(1 for v in scores if v >= 0.35)}/{len(scores)}"
    )


def main() -> None:
    root = Path(__file__).resolve().parents[2] / "recordings"
    for path in sorted(root.glob("*.csv")):
        summarize(path)


if __name__ == "__main__":
    main()
