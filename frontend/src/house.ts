import type { GeometryFix, HouseAnchor, HouseConfig, HouseFloor, HouseRoom, NodeReport } from "./types";

type Plate = {
  floor: HouseFloor;
  x: number;
  y: number;
  w: number;
  h: number;
  scale: number;
};

export class HouseView {
  private plates: Plate[] = [];
  private sweep = 0;

  constructor(private canvas: HTMLCanvasElement) {}

  layout(house: HouseConfig, cssW: number, cssH: number): Plate[] {
    const floors = [...(house.floors || [])].sort((a, b) => b.z - a.z);
    const fw = house.footprint?.w || Math.max(...floors.map((f) => f.w), 12);
    const fd = house.footprint?.d || Math.max(...floors.map((f) => f.d), 10);
    const pad = 18;
    const gap = 18;
    const labelH = 18;
    const n = Math.max(1, floors.length);
    const availH = cssH - pad * 2 - labelH * n - gap * (n - 1);
    const plateH = availH / n;
    const scale = Math.min((cssW - pad * 2) / fw, plateH / fd);
    const w = fw * scale;
    const h = fd * scale;
    const left = pad + Math.max(0, (cssW - pad * 2 - w) / 2);
    this.plates = floors.map((floor, i) => ({
      floor: { ...floor, w: fw, d: fd },
      x: left,
      y: pad + labelH + i * (h + labelH + gap),
      w,
      h,
      scale,
    }));
    return this.plates;
  }

  hit(cssX: number, cssY: number): { floor: string; x: number; y: number } | null {
    for (const plate of this.plates) {
      if (cssX < plate.x || cssY < plate.y || cssX > plate.x + plate.w || cssY > plate.y + plate.h) continue;
      return {
        floor: plate.floor.id,
        x: Math.round(((cssX - plate.x) / plate.scale) * 10) / 10,
        y: Math.round(((cssY - plate.y) / plate.scale) * 10) / 10,
      };
    }
    return null;
  }

  draw(house: HouseConfig | null, fix: GeometryFix | null, nodes: NodeReport[], now: number): void {
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
    ctx.fillStyle = "rgba(8, 18, 16, 0.96)";
    ctx.fillRect(0, 0, cssW, cssH);

    if (!house?.floors?.length) {
      ctx.fillStyle = "rgba(150, 190, 170, 0.7)";
      ctx.font = "13px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Add rooms to sketch the stacked floors.", cssW / 2, cssH / 2);
      return;
    }

    this.sweep = (this.sweep + 0.018) % (Math.PI * 2);
    const plates = this.layout(house, cssW, cssH);
    const rooms = house.rooms || [];

    for (const plate of plates) {
      this.drawFootprint(ctx, plate);
      this.drawSweep(ctx, plate);
      for (const room of rooms.filter((r) => r.floor === plate.floor.id)) {
        this.drawRoom(ctx, plate, room);
      }
    }

    for (const ring of fix?.rings || []) {
      const plate = plates.find((p) => p.floor.id === ring.floor);
      if (plate) this.drawRing(ctx, plate, ring);
    }
    for (const plate of plates) {
      for (const room of rooms.filter((r) => r.floor === plate.floor.id)) {
        this.labelRoom(ctx, plate, room);
      }
    }
    for (const anchor of house.anchors || []) {
      const plate = plates.find((p) => p.floor.id === anchor.floor);
      if (plate) this.drawAnchor(ctx, plate, anchor);
    }
    for (const cand of fix?.candidates || []) {
      const plate = plates.find((p) => p.floor.id === cand.floor);
      if (!plate || cand.x == null || cand.y == null) continue;
      this.blob(ctx, plate, cand.x, cand.y, Math.min(cand.uncertainty ?? 1.2, 3.2), "rgba(126, 203, 255, 0.12)", false);
    }

    const markers = nodes.filter((n) => n.position && n.position.x != null && n.position.y != null);
    const walker = markers.find((n) => !n.local) || markers[0];
    for (const node of markers) {
      const pos = node.position!;
      const plate = plates.find((p) => p.floor.id === (pos.floor || ""));
      if (!plate) continue;
      const primary = node === walker;
      this.blob(
        ctx,
        plate,
        Number(pos.x),
        Number(pos.y),
        Math.min(Number(pos.uncertainty ?? 1.4), 3.5),
        primary ? "rgba(110, 255, 176, 0.28)" : "rgba(255, 196, 107, 0.18)",
        primary,
      );
      this.labelYou(ctx, plate, Number(pos.x), Number(pos.y), node.local ? "this PC" : node.id, now, primary);
    }
  }

  private toPx(plate: Plate, x: number, y: number): [number, number] {
    return [plate.x + x * plate.scale, plate.y + y * plate.scale];
  }

  private clipPlate(ctx: CanvasRenderingContext2D, plate: Plate): void {
    ctx.beginPath();
    ctx.rect(plate.x, plate.y, plate.w, plate.h);
    ctx.clip();
  }

  private drawFootprint(ctx: CanvasRenderingContext2D, plate: Plate): void {
    ctx.save();
    ctx.fillStyle = "rgba(12, 22, 20, 0.95)";
    ctx.strokeStyle = "rgba(110, 230, 170, 0.22)";
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(plate.x, plate.y, plate.w, plate.h, 8);
    else ctx.rect(plate.x, plate.y, plate.w, plate.h);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(150, 190, 170, 0.72)";
    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`floor ${plate.floor.name}   z=${plate.floor.z}m`, plate.x, plate.y - 6);
    ctx.fillStyle = "rgba(150, 190, 170, 0.28)";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("rest of house", plate.x + plate.w - 8, plate.y + 16);
    ctx.restore();
  }

  private drawRoom(ctx: CanvasRenderingContext2D, plate: Plate, room: HouseRoom): void {
    const [x, y] = this.toPx(plate, room.x, room.y);
    const w = room.w * plate.scale;
    const h = room.d * plate.scale;
    ctx.save();
    ctx.fillStyle = "rgba(30, 70, 55, 0.55)";
    ctx.strokeStyle = "rgba(110, 255, 176, 0.55)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, 6);
    else ctx.rect(x, y, w, h);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  private labelRoom(ctx: CanvasRenderingContext2D, plate: Plate, room: HouseRoom): void {
    const [x, y] = this.toPx(plate, room.x, room.y);
    ctx.fillStyle = "rgba(232, 255, 244, 0.8)";
    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(room.name, x + 8, y + 16);
  }

  private drawSweep(ctx: CanvasRenderingContext2D, plate: Plate): void {
    const cx = plate.x + plate.w / 2;
    const cy = plate.y + plate.h / 2;
    const maxR = Math.hypot(plate.w, plate.h);
    ctx.save();
    this.clipPlate(ctx, plate);
    ctx.translate(cx, cy);
    ctx.rotate(this.sweep);
    const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, maxR);
    grad.addColorStop(0, "rgba(80,255,170,0.16)");
    grad.addColorStop(1, "rgba(80,255,170,0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, maxR, -0.38, 0.04);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  private drawAnchor(ctx: CanvasRenderingContext2D, plate: Plate, anchor: HouseAnchor): void {
    const [x, y] = this.toPx(plate, anchor.x, anchor.y);
    ctx.fillStyle = "#ffc46b";
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#f4ffe8";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "rgba(230, 240, 235, 0.88)";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(anchor.label, x + 8, y + 4);
  }

  private drawRing(
    ctx: CanvasRenderingContext2D,
    plate: Plate,
    ring: { x: number; y: number; r_inner: number; r_outer: number; linked?: boolean },
  ): void {
    const [x, y] = this.toPx(plate, ring.x, ring.y);
    ctx.save();
    this.clipPlate(ctx, plate);
    ctx.strokeStyle = ring.linked ? "rgba(124, 255, 184, 0.7)" : "rgba(126, 203, 255, 0.45)";
    ctx.fillStyle = ring.linked ? "rgba(124, 255, 184, 0.07)" : "rgba(126, 203, 255, 0.05)";
    ctx.beginPath();
    ctx.arc(x, y, ring.r_outer * plate.scale, 0, Math.PI * 2);
    ctx.arc(x, y, ring.r_inner * plate.scale, 0, Math.PI * 2, true);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x, y, ring.r_outer * plate.scale, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  private blob(
    ctx: CanvasRenderingContext2D,
    plate: Plate,
    mx: number,
    my: number,
    uncertainty: number,
    fill: string,
    stroke: boolean,
  ): void {
    const [x, y] = this.toPx(plate, mx, my);
    ctx.save();
    this.clipPlate(ctx, plate);
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(x, y, Math.max(12, uncertainty * plate.scale), 0, Math.PI * 2);
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = "#7cffb8";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    ctx.restore();
  }

  private labelYou(
    ctx: CanvasRenderingContext2D,
    plate: Plate,
    mx: number,
    my: number,
    text: string,
    now: number,
    primary: boolean,
  ): void {
    const [x, y] = this.toPx(plate, mx, my);
    const pulse = primary ? 2.4 + Math.sin(now * 8) * 1.4 : 0;
    ctx.beginPath();
    ctx.fillStyle = primary ? "#e8fff4" : "#ffc46b";
    ctx.arc(x, y, 4 + pulse * 0.25, 0, Math.PI * 2);
    ctx.fill();
    if (primary) {
      ctx.strokeStyle = "rgba(124,255,184,0.55)";
      ctx.beginPath();
      ctx.arc(x, y, 10 + pulse, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(232,255,244,0.85)";
    ctx.font = "11px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(text, x, y + 18);
  }
}
