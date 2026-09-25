export type HeadingSource = "gyro" | "manual" | "none";

type HeadingListener = (heading: number, source: HeadingSource) => void;

const listeners = new Set<HeadingListener>();
let started = false;
let lastGyro: number | null = null;

function emit(heading: number, source: HeadingSource): void {
  for (const listener of listeners) listener(heading, source);
}

function fromEvent(ev: DeviceOrientationEvent): number | null {
  const webkit = (ev as DeviceOrientationEvent & { webkitCompassHeading?: number }).webkitCompassHeading;
  if (typeof webkit === "number" && !Number.isNaN(webkit)) return (webkit + 360) % 360;
  if (typeof ev.alpha !== "number" || Number.isNaN(ev.alpha)) return null;
  return (360 - ev.alpha) % 360;
}

function onOrient(ev: DeviceOrientationEvent): void {
  const heading = fromEvent(ev);
  if (heading == null) return;
  lastGyro = heading;
  emit(heading, "gyro");
}

export function onHeading(listener: HeadingListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function enableGyro(): Promise<string> {
  const DOE = window.DeviceOrientationEvent as typeof DeviceOrientationEvent & {
    requestPermission?: () => Promise<string>;
  };
  if (typeof DOE.requestPermission === "function") {
    const state = await DOE.requestPermission();
    if (state !== "granted") return "compass permission denied";
  }
  if (started) return lastGyro == null ? "waiting for gyro" : "gyro";
  window.addEventListener("deviceorientationabsolute", onOrient as EventListener, true);
  window.addEventListener("deviceorientation", onOrient, true);
  started = true;
  return "listening for gyro / compass";
}

export function gyroHeading(): number | null {
  return lastGyro;
}
