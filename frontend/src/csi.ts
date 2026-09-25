import type { CsiSample } from "./types";

export class CsiHeatmap {
  private rows: number[][] = [];
  private maxRows = 72;
  private lastSeq = -1;

  constructor(private canvas: HTMLCanvasElement) {}

  push(sample: CsiSample | null): void {
    if (!sample?.amplitudes.length) return;
    if (sample.seq === this.lastSeq) return;
    this.lastSeq = sample.seq;
    this.rows.push(sample.amplitudes);
    if (this.rows.length > this.maxRows) this.rows.shift();
  }

  clear(): void {
    this.rows = [];
    this.lastSeq = -1;
  }

  draw(status: string): void {
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (this.canvas.width !== Math.floor(w * dpr) || this.canvas.height !== Math.floor(h * dpr)) {
      this.canvas.width = Math.floor(w * dpr);
      this.canvas.height = Math.floor(h * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1412";
    ctx.fillRect(0, 0, w, h);

    if (!this.rows.length) {
      ctx.fillStyle = "rgba(190,210,200,0.55)";
      ctx.font = "13px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(status || "CSI source not connected", w / 2, h / 2);
      return;
    }

    const cols = this.rows[0]?.length ?? 1;
    const cw = w / cols;
    const rh = h / this.maxRows;
    let vmin = Infinity;
    let vmax = -Infinity;
    for (const row of this.rows) {
      for (const v of row) {
        if (v < vmin) vmin = v;
        if (v > vmax) vmax = v;
      }
    }
    const span = Math.max(1e-3, vmax - vmin);
    const y0 = h - this.rows.length * rh;
    this.rows.forEach((row, i) => {
      row.forEach((v, c) => {
        const t = (v - vmin) / span;
        ctx.fillStyle = heat(t);
        ctx.fillRect(c * cw, y0 + i * rh, cw + 0.5, rh + 0.5);
      });
    });
  }
}

function heat(t: number): string {
  const x = Math.min(1, Math.max(0, t));
  const r = Math.floor(20 + 220 * x);
  const g = Math.floor(40 + 180 * (1 - Math.abs(x - 0.55)));
  const b = Math.floor(70 + 160 * (1 - x));
  return `rgb(${r},${g},${b})`;
}
