import { bandColor, bssidAngle, rssiRadius } from "./rf";
import type { AccessPoint } from "./types";

export class RadarView {
  private sweep = 0;
  private pulses = new Map<string, number>();
  private radii = new Map<string, number>();

  constructor(private canvas: HTMLCanvasElement) {}

  draw(aps: AccessPoint[], now: number): void {
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = this.canvas.clientWidth;
    const cssH = this.canvas.clientHeight;
    if (this.canvas.width !== Math.floor(cssW * dpr) || this.canvas.height !== Math.floor(cssH * dpr)) {
      this.canvas.width = Math.floor(cssW * dpr);
      this.canvas.height = Math.floor(cssH * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const cx = cssW / 2;
    const cy = cssH / 2;
    const maxR = Math.min(cx, cy) - 18;
    this.sweep = (this.sweep + 0.012) % (Math.PI * 2);

    this.rings(ctx, cx, cy, maxR);
    this.drawSweep(ctx, cx, cy, maxR);

    for (const ap of aps) {
      const angle = bssidAngle(ap.bssid);
      const rssi = ap.smoothed_rssi ?? ap.rssi;
      const target = rssiRadius(rssi, maxR);
      const prevR = this.radii.get(ap.bssid) ?? target;
      const r = prevR + (target - prevR) * 0.14;
      this.radii.set(ap.bssid, r);
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      const flicker = ap.variance > 1.1 || (ap.linked && ap.variance > 0.4);
      const prev = this.pulses.get(ap.bssid) ?? 0;
      const pulse = flicker ? Math.min(1, prev + 0.08) : Math.max(0, prev - 0.04);
      this.pulses.set(ap.bssid, pulse);
      this.blip(ctx, x, y, ap, pulse, now);
    }

    ctx.fillStyle = "#e8fff4";
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(232,255,244,0.55)";
    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("you", cx, cy + 18);
  }

  private rings(ctx: CanvasRenderingContext2D, cx: number, cy: number, maxR: number): void {
    ctx.save();
    ctx.strokeStyle = "rgba(110, 230, 170, 0.18)";
    ctx.fillStyle = "rgba(8, 18, 16, 0.92)";
    ctx.beginPath();
    ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    for (const frac of [0.25, 0.5, 0.75, 1]) {
      ctx.beginPath();
      ctx.arc(cx, cy, maxR * frac, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(cx - maxR, cy);
    ctx.lineTo(cx + maxR, cy);
    ctx.moveTo(cx, cy - maxR);
    ctx.lineTo(cx, cy + maxR);
    ctx.stroke();
    ctx.fillStyle = "rgba(150, 190, 170, 0.45)";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("−25 dBm", cx + 8, cy - maxR * 0.08);
    ctx.fillText("−95 dBm", cx + 8, cy - maxR + 12);
    ctx.restore();
  }

  private drawSweep(ctx: CanvasRenderingContext2D, cx: number, cy: number, maxR: number): void {
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
    grad.addColorStop(0, "rgba(80,255,170,0.12)");
    grad.addColorStop(1, "rgba(80,255,170,0)");
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.sweep);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, maxR, -0.35, 0.02);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  private blip(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    ap: AccessPoint,
    pulse: number,
    now: number,
  ): void {
    const color = bandColor(ap.band, ap.linked);
    const size = ap.linked ? 7 : 4.5;
    if (pulse > 0.02) {
      const glow = 10 + Math.sin(now * 10) * 4 * pulse;
      ctx.beginPath();
      ctx.fillStyle = hexAlpha(color, 0.2 * pulse);
      ctx.arc(x, y, size + glow, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
    if (ap.linked) {
      ctx.strokeStyle = "#f4ffe8";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(230,240,235,0.82)";
    ctx.font = ap.linked ? "12px 'Segoe UI', sans-serif" : "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(ap.ssid || ap.bssid, x + 10, y + 4);
  }
}

function hexAlpha(hex: string, alpha: number): string {
  const n = hex.replace("#", "");
  const r = parseInt(n.slice(0, 2), 16);
  const g = parseInt(n.slice(2, 4), 16);
  const b = parseInt(n.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
