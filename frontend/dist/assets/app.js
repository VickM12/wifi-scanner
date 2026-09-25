(() => {
  const LABELS = [
    "empty_room", "walking", "walking_across_rf_path", "person_enters", "person_leaves",
    "sitting", "standing", "door_open", "door_close", "laptop_moved", "custom",
  ];
  const root = document.querySelector("#app");
  if (!root) throw new Error("#app missing");

  root.innerHTML = `
    <header>
      <div>
        <h1>WiFi Radar</h1>
        <p class="sub">Laptop at the center. Blip range is a path-loss guess from RSSI; angle is a stable BSSID hash, not a compass bearing.</p>
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
        <p class="radar-note">Radial distance represents signal strength only. Angular position is for visual separation and does not represent physical direction.</p>
        <div class="radar-wrap"><canvas id="radar"></canvas></div>
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
          <p class="radar-note">Each machine is its own radio. Shared snapshots are RSSI + motion + AP list. Position is empty until you add rooms later.</p>
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

  function normalizeBssid(bssid) {
    const hex = bssid.toLowerCase().replace(/-/g, ":").match(/[0-9a-f]{2}/g);
    if (!hex || hex.length < 6) return bssid.toLowerCase();
    return hex.slice(0, 6).join(":");
  }
  function bssidAngle(bssid) {
    const norm = normalizeBssid(bssid);
    let hash = 2166136261;
    for (let i = 0; i < norm.length; i += 1) {
      hash ^= norm.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return ((hash >>> 0) / 0xffffffff) * Math.PI * 2;
  }
  function rssiRadius(rssi, maxR) {
    const t = (rssi - -95) / (-25 - -95);
    const clamped = Math.min(1, Math.max(0, t));
    return maxR * (0.12 + (1 - clamped) * 0.82);
  }
  function bandColor(band, linked) {
    if (linked) return "#7cffb8";
    if (band === "6") return "#d4b3ff";
    if (band === "5") return "#7ecbff";
    if (band === "2.4") return "#ffc46b";
    return "#9aa6b2";
  }
  function formatDbm(value) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return `${Number(value).toFixed(1)} dBm`;
  }
  function hexAlpha(hex, alpha) {
    const n = hex.replace("#", "");
    return `rgba(${parseInt(n.slice(0, 2), 16)},${parseInt(n.slice(2, 4), 16)},${parseInt(n.slice(4, 6), 16)},${alpha})`;
  }
  function fit(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  class RadarView {
    constructor(canvas) {
      this.canvas = canvas;
      this.sweep = 0;
      this.pulses = new Map();
      this.radii = new Map();
    }
    draw(aps, now) {
      const fitted = fit(this.canvas);
      if (!fitted) return;
      const { ctx, w, h } = fitted;
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const maxR = Math.min(cx, cy) - 18;
      this.sweep = (this.sweep + 0.012) % (Math.PI * 2);
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
      ctx.fillText("−25 dBm", cx + 8, cy - maxR * 0.08);
      ctx.fillText("−95 dBm", cx + 8, cy - maxR + 12);
      ctx.restore();
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
        const color = bandColor(ap.band, ap.linked);
        const size = ap.linked ? 7 : 4.5;
        if (pulse > 0.02) {
          ctx.beginPath();
          ctx.fillStyle = hexAlpha(color, 0.2 * pulse);
          ctx.arc(x, y, size + 10 + Math.sin(now * 10) * 4 * pulse, 0, Math.PI * 2);
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
        ctx.fillText(ap.ssid || ap.bssid, x + 10, y + 4);
      }
      ctx.fillStyle = "#e8fff4";
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(232,255,244,0.55)";
      ctx.font = "12px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("you", cx, cy + 18);
      ctx.textAlign = "left";
    }
  }

  class WaveformView {
    constructor(canvas) {
      this.canvas = canvas;
      this.points = [];
      this.windowS = 24;
    }
    push(t, rssi, motion) {
      this.points.push({
        t, rssi,
        mean: motion?.rolling_mean ?? null,
        baseline: motion?.baseline_rssi ?? null,
        sigma: motion?.noise_sigma ?? motion?.rolling_std ?? null,
        score: motion?.score ?? 0,
      });
      const cutoff = t - this.windowS;
      this.points = this.points.filter((p) => p.t >= cutoff);
    }
    draw(threshold, active) {
      const fitted = fit(this.canvas);
      if (!fitted) return;
      const { ctx, w, h } = fitted;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#0b1412";
      ctx.fillRect(0, 0, w, h);
      const split = Math.floor(h * 0.68);
      const min = -90;
      const max = -20;
      const now = this.points.at(-1)?.t ?? 0;
      const yAt = (dbm) => split - ((dbm - min) / (max - min)) * split;
      const xAt = (t) => ((t - (now - this.windowS)) / this.windowS) * w;
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
          if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
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
      const sh = h - split;
      ctx.fillStyle = "rgba(255,255,255,0.04)";
      ctx.fillRect(0, split, w, sh);
      const ys = (score) => split + sh - score * (sh - 8) - 4;
      ctx.strokeStyle = "rgba(255,255,255,0.2)";
      ctx.beginPath();
      ctx.moveTo(0, ys(threshold));
      ctx.lineTo(w, ys(threshold));
      ctx.stroke();
      if (this.points.length > 1) {
        ctx.beginPath();
        ctx.strokeStyle = active ? "#ff8a4a" : "#7ecbff";
        ctx.lineWidth = 1.4;
        this.points.forEach((p, i) => {
          const x = xAt(p.t);
          const y = ys(p.score);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(150,190,170,0.55)";
      ctx.fillText("motion score 0–1", 8, split + 12);
    }
  }

  class CsiHeatmap {
    constructor(canvas) {
      this.canvas = canvas;
      this.rows = [];
      this.maxRows = 72;
      this.lastSeq = -1;
    }
    push(sample) {
      if (!sample?.amplitudes?.length) return;
      if (sample.seq === this.lastSeq) return;
      this.lastSeq = sample.seq;
      this.rows.push(sample.amplitudes);
      if (this.rows.length > this.maxRows) this.rows.shift();
    }
    clear() {
      this.rows = [];
      this.lastSeq = -1;
    }
    draw(status) {
      const fitted = fit(this.canvas);
      if (!fitted) return;
      const { ctx, w, h } = fitted;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#0b1412";
      ctx.fillRect(0, 0, w, h);
      if (!this.rows.length) {
        ctx.fillStyle = "rgba(190,210,200,0.55)";
        ctx.font = "13px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(status || "CSI source not connected", w / 2, h / 2);
        ctx.textAlign = "left";
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
          const x = Math.min(1, Math.max(0, (v - vmin) / span));
          ctx.fillStyle = `rgb(${Math.floor(20 + 220 * x)},${Math.floor(40 + 180 * (1 - Math.abs(x - 0.55)))},${Math.floor(70 + 160 * (1 - x))})`;
          ctx.fillRect(c * cw, y0 + i * rh, cw + 0.5, rh + 0.5);
        });
      });
    }
  }

  const radar = new RadarView(document.querySelector("#radar"));
  const wave = new WaveformView(document.querySelector("#wave"));
  const csi = new CsiHeatmap(document.querySelector("#csi"));
  const statusEl = document.querySelector("#status");
  const badge = document.querySelector("#motion-badge");
  const rows = document.querySelector("#ap-rows");
  const ifaceSel = document.querySelector("#iface");
  const demoBox = document.querySelector("#demo");
  const threshIn = document.querySelector("#threshold");
  const portIn = document.querySelector("#csi-port");
  const sampleIn = document.querySelector("#sample-interval");
  const baseIn = document.querySelector("#baseline-window");
  const motionIn = document.querySelector("#motion-window");
  const noiseIn = document.querySelector("#noise-floor");
  const runBtn = document.querySelector("#toggle-run");
  const csiSrc = document.querySelector("#csi-src");
  const metrics = document.querySelector("#metrics");
  const calStatus = document.querySelector("#cal-status");
  const recStatus = document.querySelector("#rec-status");
  const recLabel = document.querySelector("#rec-label");
  const recCustom = document.querySelector("#rec-custom");
  const recFormat = document.querySelector("#rec-format");
  const nodeRows = document.querySelector("#node-rows");
  const netStatus = document.querySelector("#net-status");
  const nodeIdIn = document.querySelector("#node-id");
  const hubUrlIn = document.querySelector("#hub-url");
  const tokenIn = document.querySelector("#share-token");
  const pushBox = document.querySelector("#push-hub");

  let latest = null;
  let applying = false;
  let sortKey = "rssi";
  let sortDir = -1;

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${proto}://${location.host}/ws/live`);
    socket.addEventListener("message", (ev) => {
      latest = JSON.parse(ev.data);
      ingest(latest);
    });
    socket.addEventListener("close", () => {
      statusEl.textContent = "socket closed — retrying";
      setTimeout(connect, 800);
    });
    socket.addEventListener("error", () => socket.close());
  }

  function ingest(snap) {
    if (snap.link) wave.push(snap.t, snap.link.rssi, snap.motion);
    if (snap.csi) csi.push(snap.csi);
    else csi.clear();
    if (!applying) syncControls(snap);
    renderTable(snap);
    renderNodes(snap);
    renderMetrics(snap);
    const state = snap.motion?.state ?? "STILL";
    badge.textContent = state;
    badge.className = `badge ${state === "MOTION" ? "motion" : state === "DISTURBANCE" ? "disturb" : "off"}`;
    const bits = [
      snap.status || "idle",
      snap.link ? `${snap.link.ssid} ${formatDbm(snap.link.rssi)}` : "no link",
      snap.motion ? `score ${(snap.motion.score ?? 0).toFixed(2)}` : "",
    ];
    statusEl.innerHTML = bits.filter(Boolean).join(" · ");
    if (snap.error) statusEl.innerHTML += ` <span class="err">${snap.error}</span>`;
    csiSrc.textContent = snap.csi ? `(${snap.csi.source_id})` : "";
    const cal = snap.calibration || {};
    const base = cal.baseline_rssi != null ? `${Number(cal.baseline_rssi).toFixed(1)} dBm` : "—";
    const sig = cal.noise_sigma != null ? Number(cal.noise_sigma).toFixed(2) : "—";
    calStatus.textContent = `${cal.state ?? "idle"} · baseline ${base} · σ ${sig} · n=${cal.samples ?? 0}`;
    const rec = snap.recording || {};
    recStatus.textContent = rec.active
      ? `recording ${rec.label} · ${(rec.elapsed ?? 0).toFixed(1)}s · ${rec.samples} samples · ${rec.path ?? ""}`
      : rec.path
        ? `stopped · ${rec.samples} samples · ${rec.path}`
        : "not recording";
  }

  function num(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toFixed(digits);
  }

  function renderMetrics(snap) {
    const m = snap.motion || {};
    metrics.innerHTML = [
      ["RSSI", formatDbm(m.rssi ?? snap.link?.rssi)],
      ["Baseline", formatDbm(m.baseline_rssi)],
      ["Std Dev", num(m.rolling_std)],
      ["Z-score", num(m.z_score)],
      ["Motion Score", num(m.score)],
    ].map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
  }

  function fillIfIdle(input, value) {
    if (document.activeElement !== input && value != null) input.value = String(value);
  }

  function syncControls(snap) {
    const ids = new Set(snap.interfaces.map((i) => i.id));
    const current = [...ifaceSel.options].map((o) => o.value);
    if (current.join("|") !== ["", ...ids].join("|")) {
      ifaceSel.innerHTML = `<option value="">auto</option>` + snap.interfaces
        .map((i) => `<option value="${escapeHtml(i.id)}">${escapeHtml(i.name)}${i.connected ? " · up" : ""}</option>`)
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

  function fillTextIfIdle(input, value) {
    if (document.activeElement !== input) input.value = value;
  }

  function renderNodes(snap) {
    const net = snap.network || {};
    const ips = (net.lan_ips || []).join(", ") || "none";
    const listen = `${net.listen_host ?? "?"}:${net.listen_port ?? 8765}`;
    netStatus.textContent = net.lan_open
      ? `Listening on ${listen} · LAN IPs ${ips} · other PCs can POST here. Allow TCP ${net.listen_port} in Windows Firewall.`
      : `Listening on ${listen} (localhost only). Restart with python -m app --host 0.0.0.0 so the laptop can push. LAN IPs: ${ips}`;
    nodeRows.innerHTML = (snap.nodes || []).map((node) => {
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
    }).join("");
  }

  function renderTable(snap) {
    const list = [...snap.aps].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "boolean" && typeof bv === "boolean") return (Number(av) - Number(bv)) * sortDir;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sortDir;
      return String(av ?? "").localeCompare(String(bv ?? "")) * sortDir;
    });
    rows.innerHTML = list.map((ap) => {
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
    }).join("");
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
    ));
  }

  async function postJson(url, body) {
    applying = true;
    try {
      await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } finally {
      applying = false;
    }
  }

  runBtn.addEventListener("click", () => postJson("/api/control", { running: !(latest?.settings.running ?? true) }));
  demoBox.addEventListener("change", () => { csi.clear(); postJson("/api/control", { demo: demoBox.checked }); });
  ifaceSel.addEventListener("change", () => postJson("/api/control", { iface: ifaceSel.value || null }));
  portIn.addEventListener("change", () => postJson("/api/control", { csi_port: Number(portIn.value) }));
  threshIn.addEventListener("change", () => postJson("/api/control", { threshold: Number(threshIn.value) }));
  sampleIn.addEventListener("change", () => postJson("/api/control", { sample_interval: Number(sampleIn.value) }));
  baseIn.addEventListener("change", () => postJson("/api/control", { baseline_window: Number(baseIn.value) }));
  motionIn.addEventListener("change", () => postJson("/api/control", { motion_window: Number(motionIn.value) }));
  noiseIn.addEventListener("change", () => postJson("/api/control", { noise_floor: Number(noiseIn.value) }));
  nodeIdIn.addEventListener("change", () => postJson("/api/control", { node_id: nodeIdIn.value }));
  hubUrlIn.addEventListener("change", () => postJson("/api/control", { hub_url: hubUrlIn.value || null }));
  tokenIn.addEventListener("change", () => postJson("/api/control", { share_token: tokenIn.value }));
  pushBox.addEventListener("change", () => postJson("/api/control", { push_to_hub: pushBox.checked }));
  document.querySelector("#cal-start").addEventListener("click", () => postJson("/api/calibrate", { action: "start" }));
  document.querySelector("#cal-stop").addEventListener("click", () => postJson("/api/calibrate", { action: "stop" }));
  document.querySelector("#cal-reset").addEventListener("click", () => postJson("/api/calibrate", { action: "reset" }));
  document.querySelector("#rec-start").addEventListener("click", () => postJson("/api/record", {
    action: "start",
    label: recLabel.value,
    custom_label: recCustom.value || null,
    format: recFormat.value,
  }));
  document.querySelector("#rec-stop").addEventListener("click", () => postJson("/api/record", { action: "stop" }));
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
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

  function frame() {
    const snap = latest;
    radar.draw(snap?.aps ?? [], performance.now() / 1000);
    wave.draw(snap?.settings?.threshold ?? 0.35, Boolean(snap?.motion?.active));
    csi.draw(snap?.csi_status || "CSI source not connected");
    requestAnimationFrame(frame);
  }

  connect();
  requestAnimationFrame(frame);
})();
