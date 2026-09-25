import { CsiHeatmap } from "./csi";
import { enableGyro, onHeading } from "./orientation";
import { RadarView } from "./radar";
import { formatDbm } from "./rf";
import "./styles.css";
import type { AccessPoint, Snapshot } from "./types";
import { WaveformView } from "./waveform";

const LABELS = [
  "empty_room",
  "walking",
  "walking_across_rf_path",
  "person_enters",
  "person_leaves",
  "sitting",
  "standing",
  "door_open",
  "door_close",
  "laptop_moved",
  "custom",
];

const root = document.querySelector("#app");
if (!root) throw new Error("#app missing");

root.innerHTML = `
  <header>
    <div>
      <h1>WiFi Radar</h1>
      <p class="sub">You are the center. Up on the radar is the way you are facing. Gyro/compass rotates the plot; lock the linked AP ahead so a turn puts it behind you.</p>
    </div>
    <div class="controls">
      <button id="toggle-run" type="button">Pause</button>
      <label class="check"><input id="demo" type="checkbox" /> Demo</label>
      <label>Interface
        <select id="iface"><option value="">auto</option></select>
      </label>
      <label>CSI UDP port
        <input id="csi-port" type="number" min="1024" max="65535" step="1" value="5500" />
      </label>
    </div>
  </header>
  <div class="status-bar">
    <span id="status">connecting…</span>
    <span id="motion-badge" class="badge off">STILL</span>
  </div>
  <div class="layout">
    <section class="panel">
      <h2>AP radar</h2>
      <div class="legend">
        <span><i class="swatch" style="background:#7cffb8"></i>linked</span>
        <span><i class="swatch" style="background:#ffc46b"></i>2.4 GHz</span>
        <span><i class="swatch" style="background:#7ecbff"></i>5 GHz</span>
        <span><i class="swatch" style="background:#d4b3ff"></i>6 GHz</span>
        <span>pulse = scan-to-scan flicker</span>
      </div>
      <p class="radar-note" id="radar-note">Range is RSSI. Up is facing. Chrome blocks the gyro on HTTP — use the HTTPS phone link under Network nodes, accept the warning, then Enable gyro. The heading slider always works.</p>
      <div class="radar-wrap" id="signal-wrap"><canvas id="radar"></canvas></div>
      <div class="toolbar" id="heading-bar">
        <button id="enable-gyro" type="button">Enable gyro / compass</button>
        <button id="lock-ahead" type="button">Lock linked AP ahead</button>
        <label>Heading
          <input id="heading" type="range" min="0" max="359" step="1" value="0" />
        </label>
        <span id="heading-readout" class="hint">0° · manual</span>
      </div>
    </section>
    <div class="stack">
      <section class="panel">
        <h2>Connected RSSI + motion</h2>
        <div class="metrics" id="metrics"></div>
        <canvas id="wave" class="plot"></canvas>
        <div class="toolbar">
          <label>Sample s <input id="sample-interval" type="number" min="0.05" max="2" step="0.05" value="0.15" /></label>
          <label>Baseline s <input id="baseline-window" type="number" min="2" max="60" step="0.5" value="12" /></label>
          <label>Motion s <input id="motion-window" type="number" min="0.3" max="10" step="0.1" value="1.5" /></label>
          <label>Noise floor <input id="noise-floor" type="number" min="0.05" max="5" step="0.05" value="0.4" /></label>
          <label>Threshold <input id="threshold" type="number" min="0.05" max="1" step="0.05" value="0.35" /></label>
        </div>
        <div class="toolbar">
          <button id="cal-start" type="button">Start Baseline Calibration</button>
          <button id="cal-stop" type="button">Stop Calibration</button>
          <button id="cal-reset" type="button">Reset Baseline</button>
          <span id="cal-status" class="hint"></span>
        </div>
        <div class="toolbar">
          <button id="rec-start" type="button">Start Recording</button>
          <button id="rec-stop" type="button">Stop Recording</button>
          <label>Label
            <select id="rec-label">${LABELS.map((l) => `<option value="${l}">${l}</option>`).join("")}</select>
          </label>
          <label class="custom-label">Custom <input id="rec-custom" type="text" placeholder="custom label" /></label>
          <label>Format
            <select id="rec-format"><option value="csv">csv</option><option value="jsonl">jsonl</option></select>
          </label>
          <span id="rec-status" class="hint"></span>
        </div>
      </section>
      <section class="panel">
        <h2>Network nodes</h2>
        <p class="radar-note">Each machine is its own radio. Shared snapshots are RSSI + motion + AP list.</p>
        <div class="toolbar">
          <label>Name <input id="node-id" type="text" /></label>
          <label>Hub URL <input id="hub-url" type="text" placeholder="http://192.168.1.20:8765" /></label>
          <label>Token <input id="share-token" type="text" placeholder="optional" /></label>
          <label class="check"><input id="push-hub" type="checkbox" /> Push to hub</label>
        </div>
        <p id="net-status" class="hint"></p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Node</th><th>Where</th><th>SSID</th><th>BSSID</th>
                <th>RSSI</th><th>State</th><th>Score</th><th>APs</th>
              </tr>
            </thead>
            <tbody id="node-rows"></tbody>
          </table>
        </div>
      </section>
      <section class="panel">
        <h2>CSI heatmap <span id="csi-src"></span></h2>
        <canvas id="csi" class="plot"></canvas>
      </section>
      <section class="panel">
        <h2>Access points</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th data-sort="ssid">SSID</th>
                <th data-sort="bssid">BSSID</th>
                <th data-sort="channel">Ch</th>
                <th data-sort="band">Band</th>
                <th data-sort="rssi">RSSI</th>
                <th data-sort="smoothed_rssi">Smooth</th>
                <th data-sort="variance">Var</th>
                <th data-sort="last_seen">Last seen</th>
                <th data-sort="linked">Conn</th>
              </tr>
            </thead>
            <tbody id="ap-rows"></tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
  <p class="help">
    RSSI flicker on one laptop and one router detects motion on that RF path — not room-by-room occupancy.
    CSI is only shown when a real source (for example an ESP32) sends data. The laptop radio cannot provide CSI.
    Hub/node token is saved in gitignored <code>backend/radar.local.json</code> (or <code>WIFI_RADAR_TOKEN</code>), not in git. Desktop: <code>python -m app --host 0.0.0.0</code>. Laptop: <code>python -m app --hub http://DESKTOP_LAN_IP:8765</code>.
  </p>
`;

const radar = new RadarView(document.querySelector("#radar")!);
const wave = new WaveformView(document.querySelector("#wave")!);
const csi = new CsiHeatmap(document.querySelector("#csi")!);
const headingIn = document.querySelector("#heading") as HTMLInputElement;
const headingReadout = document.querySelector("#heading-readout")!;
const LOCK_KEY = "radar-ap-bearings";
const statusEl = document.querySelector("#status")!;
const badge = document.querySelector("#motion-badge")!;
const rows = document.querySelector("#ap-rows")!;
const ifaceSel = document.querySelector("#iface") as HTMLSelectElement;
const demoBox = document.querySelector("#demo") as HTMLInputElement;
const threshIn = document.querySelector("#threshold") as HTMLInputElement;
const portIn = document.querySelector("#csi-port") as HTMLInputElement;
const sampleIn = document.querySelector("#sample-interval") as HTMLInputElement;
const baseIn = document.querySelector("#baseline-window") as HTMLInputElement;
const motionIn = document.querySelector("#motion-window") as HTMLInputElement;
const noiseIn = document.querySelector("#noise-floor") as HTMLInputElement;
const runBtn = document.querySelector("#toggle-run") as HTMLButtonElement;
const csiSrc = document.querySelector("#csi-src")!;
const metrics = document.querySelector("#metrics")!;
const calStatus = document.querySelector("#cal-status")!;
const recStatus = document.querySelector("#rec-status")!;
const recLabel = document.querySelector("#rec-label") as HTMLSelectElement;
const recCustom = document.querySelector("#rec-custom") as HTMLInputElement;
const recFormat = document.querySelector("#rec-format") as HTMLSelectElement;
const nodeRows = document.querySelector("#node-rows")!;
const netStatus = document.querySelector("#net-status")!;
const nodeIdIn = document.querySelector("#node-id") as HTMLInputElement;
const hubUrlIn = document.querySelector("#hub-url") as HTMLInputElement;
const tokenIn = document.querySelector("#share-token") as HTMLInputElement;
const pushBox = document.querySelector("#push-hub") as HTMLInputElement;

let latest: Snapshot | null = null;
let applying = false;
let sortKey: keyof AccessPoint | "linked" = "rssi";
let sortDir = -1;
let headingDeg = 0;
let headingSource: "gyro" | "compass" | "manual" | "none" = "none";
let headingLocks: Record<string, number> = {};
try {
  headingLocks = JSON.parse(localStorage.getItem(LOCK_KEY) || "{}") as Record<string, number>;
} catch {
  headingLocks = {};
}

function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/live`;
}

function connect(): void {
  const socket = new WebSocket(wsUrl());
  socket.addEventListener("open", () => {
    statusEl.textContent = "live";
  });
  socket.addEventListener("message", (ev) => {
    latest = JSON.parse(ev.data) as Snapshot;
    ingest(latest);
  });
  socket.addEventListener("close", () => {
    statusEl.textContent = "socket closed — retrying";
    setTimeout(connect, 800);
  });
  socket.addEventListener("error", () => socket.close());
}

function ingest(snap: Snapshot): void {
  if (snap.link) wave.push(snap.t, snap.link.rssi, snap.motion);
  if (snap.csi) csi.push(snap.csi);
  else csi.clear();
  if (!applying) {
    syncControls(snap);
  }
  renderTable(snap);
  renderNodes(snap);
  renderMetrics(snap);
  const state = snap.motion?.state ?? "STILL";
  badge.textContent = state;
  badge.className = `badge ${stateClass(state)}`;
  const bits = [
    snap.status || "idle",
    snap.link ? `${snap.link.ssid} ${formatDbm(snap.link.rssi)}` : "no link",
    snap.motion ? `score ${(snap.motion.score ?? 0).toFixed(2)}` : "",
  ];
  statusEl.innerHTML = bits.filter(Boolean).join(" · ");
  if (snap.error) {
    statusEl.innerHTML += ` <span class="err">${snap.error}</span>`;
  }
  csiSrc.textContent = snap.csi ? `(${snap.csi.source_id})` : "";
  const cal = snap.calibration;
  const base = cal?.baseline_rssi != null ? `${cal.baseline_rssi.toFixed(1)} dBm` : "—";
  const sig = cal?.noise_sigma != null ? cal.noise_sigma.toFixed(2) : "—";
  calStatus.textContent = `${cal?.state ?? "idle"} · baseline ${base} · σ ${sig} · n=${cal?.samples ?? 0}`;
  const rec = snap.recording;
  const elapsed = rec ? rec.elapsed.toFixed(1) : "0.0";
  recStatus.textContent = rec?.active
    ? `recording ${rec.label} · ${elapsed}s · ${rec.samples} samples · ${rec.path ?? ""}`
    : rec?.path
      ? `stopped · ${rec.samples} samples · ${rec.path}`
      : "not recording";
}

function stateClass(state: string): string {
  if (state === "MOTION") return "motion";
  if (state === "DISTURBANCE") return "disturb";
  return "off";
}

function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function renderMetrics(snap: Snapshot): void {
  const m = snap.motion;
  metrics.innerHTML = [
    ["RSSI", formatDbm(m?.rssi ?? snap.link?.rssi)],
    ["Baseline", formatDbm(m?.baseline_rssi)],
    ["Std Dev", num(m?.rolling_std)],
    ["Z-score", num(m?.z_score)],
    ["Motion Score", num(m?.score)],
  ]
    .map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`)
    .join("");
}

function syncControls(snap: Snapshot): void {
  const ids = new Set(snap.interfaces.map((i) => i.id));
  const current = [...ifaceSel.options].map((o) => o.value);
  const wanted = ["", ...ids];
  if (current.join("|") !== wanted.join("|")) {
    ifaceSel.innerHTML = `<option value="">auto</option>` + snap.interfaces
      .map((i) => `<option value="${escapeAttr(i.id)}">${escapeHtml(i.name)}${i.connected ? " · up" : ""}</option>`)
      .join("");
  }
  ifaceSel.value = snap.settings.iface ?? "";
  demoBox.checked = snap.settings.demo;
  fillIfIdle(threshIn, snap.settings.threshold);
  fillIfIdle(portIn, snap.settings.csi_port);
  fillIfIdle(sampleIn, snap.settings.sample_interval);
  fillIfIdle(baseIn, snap.settings.baseline_window);
  fillIfIdle(motionIn, snap.settings.motion_window);
  fillIfIdle(noiseIn, snap.settings.noise_floor);
  fillTextIfIdle(nodeIdIn, snap.settings.node_id ?? "");
  fillTextIfIdle(hubUrlIn, snap.settings.hub_url ?? "");
  fillTextIfIdle(tokenIn, snap.settings.share_token ?? "");
  pushBox.checked = Boolean(snap.settings.push_to_hub);
  runBtn.textContent = snap.settings.running ? "Pause" : "Resume";
}

function fillIfIdle(input: HTMLInputElement, value: number): void {
  if (document.activeElement !== input) input.value = String(value);
}

function fillTextIfIdle(input: HTMLInputElement, value: string): void {
  if (document.activeElement !== input) input.value = value;
}

function setHeading(value: number, source: "gyro" | "compass" | "manual" | "none"): void {
  headingDeg = ((value % 360) + 360) % 360;
  headingSource = source;
  if (document.activeElement !== headingIn) headingIn.value = String(Math.round(headingDeg));
  headingReadout.textContent = `${Math.round(headingDeg)}° · ${source}`;
}

function renderNodes(snap: Snapshot): void {
  const net = snap.network;
  const ips = (net?.lan_ips || []).join(", ") || "none";
  const listen = `${net?.listen_host ?? "?"}:${net?.listen_port ?? 8765}`;
  const logs = (net?.remote_log?.nodes || [])
    .map((n) => `${n.id} ${n.samples} samples`)
    .join(" · ");
  const https = (net?.https_urls || []).join(" or ");
  const listenLine = net?.lan_open
    ? `Listening on ${listen} · LAN IPs ${ips} · other PCs can POST here. Allow TCP ${net.listen_port}${net.https_port ? ` and ${net.https_port}` : ""} in Windows Firewall.`
    : `Listening on ${listen} (localhost only). Restart with python -m app --host 0.0.0.0 so the laptop can push. LAN IPs: ${ips}`;
  const httpsLine = https
    ? ` Phone gyro: open ${https} , accept the certificate warning, then Enable gyro.`
    : "";
  netStatus.textContent = logs
    ? `${listenLine}${httpsLine} Remote log: ${net?.remote_log?.directory} (${logs}).`
    : `${listenLine}${httpsLine} Remote snapshots are saved under recordings/remote/.`;
  nodeRows.innerHTML = (snap.nodes || [])
    .map((node) => {
      const link = node.link;
      const motion = node.motion || {};
      return `<tr class="${node.local ? "linked" : ""}">
        <td>${escapeHtml(node.id)}</td>
        <td>${node.local ? "this PC" : "remote"}</td>
        <td>${escapeHtml(link?.ssid || "—")}</td>
        <td>${escapeHtml(link?.bssid || "—")}</td>
        <td>${link?.rssi == null ? "—" : Number(link.rssi).toFixed(1)}</td>
        <td>${escapeHtml(motion.state || "—")}</td>
        <td>${motion.score == null ? "—" : Number(motion.score).toFixed(2)}</td>
        <td>${node.aps?.length ?? 0}</td>
      </tr>`;
    })
    .join("");
}

function renderTable(snap: Snapshot): void {
  const list = [...snap.aps].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (typeof av === "boolean" && typeof bv === "boolean") return (Number(av) - Number(bv)) * sortDir;
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
    return String(av ?? "").localeCompare(String(bv ?? "")) * sortDir;
  });
  rows.innerHTML = list
    .map((ap) => {
      const age = ap.last_seen ? `${Math.max(0, snap.t - ap.last_seen).toFixed(1)}s` : "—";
      return `<tr class="${ap.linked ? "linked" : ""}">
        <td>${escapeHtml(ap.ssid)}</td>
        <td>${escapeHtml(ap.bssid)}</td>
        <td>${ap.channel || "—"}</td>
        <td>${escapeHtml(ap.band)}</td>
        <td>${ap.rssi.toFixed(1)}</td>
        <td>${ap.smoothed_rssi == null ? "—" : ap.smoothed_rssi.toFixed(1)}</td>
        <td>${ap.variance.toFixed(2)}</td>
        <td>${age}</td>
        <td>${ap.linked ? "yes" : "no"}</td>
      </tr>`;
    })
    .join("");
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch] ?? ch
  ));
}

function escapeAttr(value: string): string {
  return escapeHtml(value);
}

async function postJson(url: string, body: Record<string, unknown>): Promise<void> {
  applying = true;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } finally {
    applying = false;
  }
}

function postControl(body: Record<string, unknown>): void {
  void postJson("/api/control", body);
}

runBtn.addEventListener("click", () => {
  postControl({ running: !(latest?.settings.running ?? true) });
});
demoBox.addEventListener("change", () => {
  csi.clear();
  postControl({ demo: demoBox.checked });
});
ifaceSel.addEventListener("change", () => postControl({ iface: ifaceSel.value || null }));
portIn.addEventListener("change", () => postControl({ csi_port: Number(portIn.value) }));
threshIn.addEventListener("change", () => postControl({ threshold: Number(threshIn.value) }));
sampleIn.addEventListener("change", () => postControl({ sample_interval: Number(sampleIn.value) }));
baseIn.addEventListener("change", () => postControl({ baseline_window: Number(baseIn.value) }));
motionIn.addEventListener("change", () => postControl({ motion_window: Number(motionIn.value) }));
noiseIn.addEventListener("change", () => postControl({ noise_floor: Number(noiseIn.value) }));
nodeIdIn.addEventListener("change", () => postControl({ node_id: nodeIdIn.value }));
hubUrlIn.addEventListener("change", () => postControl({ hub_url: hubUrlIn.value || null }));
tokenIn.addEventListener("change", () => postControl({ share_token: tokenIn.value }));
pushBox.addEventListener("change", () => postControl({ push_to_hub: pushBox.checked }));
headingIn.addEventListener("input", () => setHeading(Number(headingIn.value), "manual"));
document.querySelector("#enable-gyro")!.addEventListener("click", () => {
  void enableGyro().then((msg) => {
    headingReadout.textContent = `${Math.round(headingDeg)}° · ${msg}`;
  });
});
document.querySelector("#radar")!.addEventListener("click", () => {
  void enableGyro().then((msg) => {
    headingReadout.textContent = `${Math.round(headingDeg)}° · ${msg}`;
  });
});
document.querySelector("#lock-ahead")!.addEventListener("click", () => {
  const bssid = latest?.link?.bssid;
  if (!bssid) {
    headingReadout.textContent = `${Math.round(headingDeg)}° · no linked AP`;
    return;
  }
  headingLocks[bssid.toLowerCase()] = headingDeg;
  localStorage.setItem(LOCK_KEY, JSON.stringify(headingLocks));
  headingReadout.textContent = `${Math.round(headingDeg)}° · locked ${bssid.slice(-8)} ahead`;
});
onHeading((value, source) => setHeading(value, source));

document.querySelector("#cal-start")!.addEventListener("click", () => {
  void postJson("/api/calibrate", { action: "start" });
});
document.querySelector("#cal-stop")!.addEventListener("click", () => {
  void postJson("/api/calibrate", { action: "stop" });
});
document.querySelector("#cal-reset")!.addEventListener("click", () => {
  void postJson("/api/calibrate", { action: "reset" });
});
document.querySelector("#rec-start")!.addEventListener("click", () => {
  const label = recLabel.value;
  void postJson("/api/record", {
    action: "start",
    label,
    custom_label: recCustom.value || null,
    format: recFormat.value,
  });
});
document.querySelector("#rec-stop")!.addEventListener("click", () => {
  void postJson("/api/record", { action: "stop" });
});

document.querySelectorAll<HTMLTableCellElement>("th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort as keyof AccessPoint;
    if (sortKey === key) sortDir *= -1;
    else {
      sortKey = key;
      sortDir = key === "ssid" || key === "bssid" || key === "band" ? 1 : -1;
    }
    document.querySelectorAll("th[data-sort]").forEach((el) => el.classList.remove("active"));
    th.classList.add("active");
    if (latest) renderTable(latest);
  });
});

function frame(): void {
  const snap = latest;
  const now = performance.now() / 1000;
  if (headingSource === "none" && snap?.heading != null) {
    setHeading(snap.heading, "gyro");
  }
  radar.draw(snap?.aps ?? [], now, headingDeg, headingLocks);
  wave.draw(snap?.settings.threshold ?? 0.35, Boolean(snap?.motion?.active));
  csi.draw(snap?.csi_status || "CSI source not connected");
  requestAnimationFrame(frame);
}

connect();
requestAnimationFrame(frame);
