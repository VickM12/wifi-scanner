export type HeadingSource = "gyro" | "compass" | "manual" | "none";

type HeadingListener = (heading: number, source: HeadingSource) => void;

const listeners = new Set<HeadingListener>();
let started = false;
let lastGyro: number | null = null;
let lastSource: HeadingSource = "none";
let yaw = 0;
let lastMotionT = 0;
let gotOrient = false;
let gotMotion = false;

function emit(heading: number, source: HeadingSource): void {
  lastGyro = heading;
  lastSource = source;
  for (const listener of listeners) listener(heading, source);
}

function screenOffset(): number {
  const raw = (screen.orientation && screen.orientation.angle) || (window as Window & { orientation?: number }).orientation || 0;
  return Number(raw) || 0;
}

function fromOrient(ev: DeviceOrientationEvent): number | null {
  const webkit = (ev as DeviceOrientationEvent & { webkitCompassHeading?: number }).webkitCompassHeading;
  if (typeof webkit === "number" && !Number.isNaN(webkit)) {
    return (webkit + screenOffset() + 360) % 360;
  }
  if (typeof ev.alpha !== "number" || Number.isNaN(ev.alpha)) return null;
  return (360 - ev.alpha + screenOffset()) % 360;
}

function onOrient(ev: DeviceOrientationEvent): void {
  const heading = fromOrient(ev);
  if (heading == null) return;
  gotOrient = true;
  yaw = heading;
  emit(heading, "compass");
}

function onMotion(ev: DeviceMotionEvent): void {
  const rate = ev.rotationRate;
  if (!rate) return;
  const now = performance.now();
  const dt = lastMotionT ? Math.min(0.1, (now - lastMotionT) / 1000) : 0;
  lastMotionT = now;
  if (!dt) return;
  const grav = ev.accelerationIncludingGravity;
  const flat = Math.abs(grav?.z ?? 0) > 8;
  const spin = flat ? rate.alpha : (rate.alpha ?? rate.gamma);
  if (typeof spin !== "number" || Number.isNaN(spin)) return;
  gotMotion = true;
  if (gotOrient) return;
  yaw = (yaw + spin * dt + 360) % 360;
  emit(yaw, "gyro");
}

export function onHeading(listener: HeadingListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function enableGyro(): Promise<string> {
  const DOE = window.DeviceOrientationEvent as typeof DeviceOrientationEvent & {
    requestPermission?: () => Promise<string>;
  };
  const DME = window.DeviceMotionEvent as typeof DeviceMotionEvent & {
    requestPermission?: () => Promise<string>;
  };
  if (typeof DOE.requestPermission === "function") {
    const state = await DOE.requestPermission();
    if (state !== "granted") return "compass permission denied — use the heading slider";
  }
  if (typeof DME.requestPermission === "function") {
    const state = await DME.requestPermission();
    if (state !== "granted") return "motion permission denied — use the heading slider";
  }
  if (!started) {
    window.addEventListener("deviceorientationabsolute", onOrient as EventListener, true);
    window.addEventListener("deviceorientation", onOrient, true);
    window.addEventListener("devicemotion", onMotion, true);
    started = true;
  }
  await new Promise((resolve) => window.setTimeout(resolve, 700));
  if (gotOrient) return "compass live";
  if (gotMotion) return "gyro live (no compass)";
  const insecure = location.protocol !== "https:" && location.hostname !== "localhost" && location.hostname !== "127.0.0.1";
  if (insecure) return "Chrome blocks motion sensors on HTTP. Open the HTTPS link in Network nodes, accept the warning, then tap Enable again";
  return "no sensor events yet — allow motion permission, or drag the heading slider";
}

export function gyroHeading(): number | null {
  return lastGyro;
}

export function headingLabel(): HeadingSource {
  return lastSource;
}
