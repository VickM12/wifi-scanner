export function normalizeBssid(bssid: string): string {
  const hex = bssid.toLowerCase().replace(/-/g, ":").match(/[0-9a-f]{2}/g);
  if (!hex || hex.length < 6) return bssid.toLowerCase();
  return hex.slice(0, 6).join(":");
}

export function bssidAngle(bssid: string): number {
  const norm = normalizeBssid(bssid);
  let hash = 2166136261;
  for (let i = 0; i < norm.length; i += 1) {
    hash ^= norm.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) / 0xffffffff) * Math.PI * 2;
}

export function rssiRadius(rssi: number, maxR: number): number {
  const minDbm = -95;
  const maxDbm = -25;
  const t = (rssi - minDbm) / (maxDbm - minDbm);
  const clamped = Math.min(1, Math.max(0, t));
  // Stronger signal closer to the laptop at the origin.
  return maxR * (0.12 + (1 - clamped) * 0.82);
}

export function bandColor(band: string, linked: boolean): string {
  if (linked) return "#7cffb8";
  if (band === "6") return "#d4b3ff";
  if (band === "5") return "#7ecbff";
  if (band === "2.4") return "#ffc46b";
  return "#9aa6b2";
}

export function formatDbm(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)} dBm`;
}
