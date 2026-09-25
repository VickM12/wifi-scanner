import type { MotionResult } from "./types";

type Point = {
  t: number;
  rssi: number;
  mean: number | null;
  baseline: number | null;
  sigma: number | null;
  score: number;
};

export class WaveformView {
  private points: Point[] = [];
  private windowS = 24;

  constructor(private canvas: HTMLCanvasElement) {}

  push(t: number, rssi: number, motion: MotionResult | null): void {
    this.points.push({
      t,
      rssi,
      mean: motion?.rolling_mean ?? null,
      baseline: motion?.baseline_rssi ?? null,
      sigma: motion?.noise_sigma ?? motion?.rolling_std ?? null,
      score: motion?.score ?? 0,
    });
    const cutoff = t - this.windowS;
    this.points = this.points.filter((p) => p.t >= cutoff);
  }

  draw(threshold: number, active: boolean): void {
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

    const split = Math.floor(h * 0.68);
    this.rssiPlot(ctx, w, split, active);
    this.scorePlot(ctx, w, split, h, threshold, active);
  }

  private rssiPlot(ctx: CanvasRenderingContext2D, w: number, h: number, active: boolean): void {
    const min = -90;
    const max = -20;
    const now = this.points.at(-1)?.t ?? 0;
    const yAt = (dbm: number) => h - ((dbm - min) / (max - min)) * h;
    const xAt = (t: number) => ((t - (now - this.windowS)) / this.windowS) * w;

    ctx.strokeStyle = "rgba(120,160,140,0.2)";
    ctx.beginPath();
    for (const dbm of [-80, -60, -40]) {
      ctx.moveTo(0, yAt(dbm));
      ctx.lineTo(w, yAt(dbm));
    }
    ctx.stroke();

    const last = this.points.at(-1);
    if (last?.baseline != null && last.sigma != null && last.sigma > 0) {
      const top = yAt(last.baseline + 2 * last.sigma);
      const bot = yAt(last.baseline - 2 * last.sigma);
      ctx.fillStyle = "rgba(110, 180, 150, 0.10)";
      ctx.fillRect(0, Math.min(top, bot), w, Math.abs(bot - top));
      ctx.strokeStyle = "rgba(160, 200, 180, 0.35)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, yAt(last.baseline));
      ctx.lineTo(w, yAt(last.baseline));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (this.points.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = "rgba(180, 210, 200, 0.7)";
      ctx.lineWidth = 1.2;
      let started = false;
      this.points.forEach((p) => {
        if (p.mean == null) return;
        const x = xAt(p.t);
        const y = yAt(p.mean);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else ctx.lineTo(x, y);
      });
      ctx.stroke();

      ctx.beginPath();
      ctx.strokeStyle = active ? "#ffb14a" : "#6effb0";
      ctx.lineWidth = 1.6;
      this.points.forEach((p, i) => {
        const x = xAt(p.t);
        const y = yAt(p.rssi);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(150,190,170,0.55)";
    ctx.font = "10px 'Segoe UI', sans-serif";
    ctx.fillText("RSSI  raw + mean  ±2σ baseline", 8, 12);
  }

  private scorePlot(
    ctx: CanvasRenderingContext2D,
    w: number,
    top: number,
    h: number,
    threshold: number,
    active: boolean,
  ): void {
    const sh = h - top;
    ctx.fillStyle = "rgba(255,255,255,0.04)";
    ctx.fillRect(0, top, w, sh);
    const now = this.points.at(-1)?.t ?? 0;
    const yAt = (score: number) => top + sh - score * (sh - 8) - 4;
    const xAt = (t: number) => ((t - (now - this.windowS)) / this.windowS) * w;

    ctx.strokeStyle = "rgba(255,255,255,0.2)";
    ctx.beginPath();
    ctx.moveTo(0, yAt(threshold));
    ctx.lineTo(w, yAt(threshold));
    ctx.stroke();

    if (this.points.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = active ? "#ff8a4a" : "#7ecbff";
      ctx.lineWidth = 1.4;
      this.points.forEach((p, i) => {
        const x = xAt(p.t);
        const y = yAt(p.score);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(150,190,170,0.55)";
    ctx.font = "10px 'Segoe UI', sans-serif";
    ctx.fillText("motion score 0–1", 8, top + 12);
  }
}
