export type AccessPoint = {
  ssid: string;
  bssid: string;
  rssi: number;
  channel: number;
  frequency_mhz: number;
  band: string;
  linked: boolean;
  quality: number | null;
  delta_rssi: number | null;
  variance: number;
  smoothed_rssi: number | null;
  last_seen: number | null;
  bearing_deg?: number | null;
};

export type LinkSample = {
  bssid: string;
  ssid: string;
  rssi: number;
  frequency_mhz: number | null;
  raw_rssi: number | null;
  channel: number | null;
  band: string | null;
};

export type MotionResult = {
  score: number;
  rssi_score: number;
  csi_score: number;
  active: boolean;
  residual: number;
  sample_count: number;
  rssi: number | null;
  rolling_mean: number | null;
  rolling_std: number | null;
  z_score: number | null;
  short_variance: number | null;
  state: "STILL" | "DISTURBANCE" | "MOTION" | string;
  baseline_rssi: number | null;
  noise_sigma: number | null;
};

export type CsiSample = {
  timestamp: number;
  source_id: string;
  bssid: string;
  channel: number | null;
  rssi: number | null;
  subcarrier_indices: number[];
  amplitudes: number[];
  phases: number[] | null;
  seq: number;
};

export type WlanInterface = {
  id: string;
  name: string;
  connected: boolean;
};

export type AppSettings = {
  running: boolean;
  demo: boolean;
  threshold: number;
  iface: string | null;
  csi_port: number;
  sample_interval: number;
  baseline_window: number;
  motion_window: number;
  noise_floor: number;
  node_id: string;
  hub_url: string | null;
  share_token: string;
  push_to_hub: boolean;
};

export type NodeReport = {
  id: string;
  t: number;
  local?: boolean;
  link: LinkSample | null;
  motion: {
    rssi: number | null;
    score: number | null;
    state: string;
    z_score: number | null;
    residual: number | null;
    rolling_mean: number | null;
    rolling_std: number | null;
  };
  aps: Array<{
    ssid: string;
    bssid: string;
    rssi: number;
    channel: number;
    band: string;
    linked: boolean;
  }>;
  position: GeometryFix | null;
};

export type HouseFloor = {
  id: string;
  name: string;
  z: number;
  w: number;
  d: number;
};

export type HouseAnchor = {
  id: string;
  label: string;
  floor: string;
  x: number;
  y: number;
  bssids: string[];
};

export type HouseRoom = {
  id: string;
  name: string;
  floor: string;
  z: number;
  x: number;
  y: number;
  w: number;
  d: number;
};

export type HouseConfig = {
  footprint?: { w: number; d: number };
  floors: HouseFloor[];
  rooms?: HouseRoom[];
  anchors: HouseAnchor[];
};

export type GeometryFix = {
  x?: number | null;
  y?: number | null;
  z?: number | null;
  room?: string | null;
  floor?: string | null;
  uncertainty?: number | null;
  score?: number | null;
  candidates?: Array<{
    x: number;
    y: number;
    z: number;
    floor: string;
    room: string;
    uncertainty: number;
    score: number;
  }>;
  rings?: Array<{
    anchor_id: string;
    label: string;
    floor: string;
    x: number;
    y: number;
    r_inner: number;
    r_outer: number;
    rssi: number;
    band?: string | null;
    linked?: boolean;
  }>;
};

export type NetworkInfo = {
  listen_host: string;
  listen_port: number;
  https_port?: number | null;
  https_urls?: string[];
  lan_ips: string[];
  lan_open: boolean;
  remote_log?: {
    enabled: boolean;
    directory: string;
    nodes: Array<{ id: string; samples: number; path: string | null }>;
  };
};

export type CalibrationStatus = {
  state: string;
  bssid: string | null;
  baseline_rssi: number | null;
  noise_sigma: number | null;
  samples: number;
};

export type RecordingStatus = {
  active: boolean;
  label: string;
  elapsed: number;
  samples: number;
  path: string | null;
  format: string;
  labels: string[];
};

export type Snapshot = {
  t: number;
  link: LinkSample | null;
  aps: AccessPoint[];
  motion: MotionResult | null;
  csi: CsiSample | null;
  interfaces: WlanInterface[];
  settings: AppSettings;
  status: string;
  error: string | null;
  calibration: CalibrationStatus;
  recording: RecordingStatus;
  csi_status: string;
  nodes: NodeReport[];
  network: NetworkInfo;
  house?: HouseConfig | null;
  fix?: GeometryFix | null;
  heading?: number | null;
};
