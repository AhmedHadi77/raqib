// Mirrors backend/app/schemas.py (contract-first). Keep in sync when the schema version changes.

export type RobotState = 'IDLE' | 'MANUAL' | 'AUTONOMOUS_PATROL' | 'EMERGENCY_STOP' | 'SAFE_HOLD';

export interface EnvironmentReading {
  temperature_c: number;
  humidity_pct: number;
  pressure_hpa?: number;
  aqi: number | null;
  aqi_label: string;
  mq135_ppm?: number | null;
  comfort_verdict: string;
  gas_verdict: 'NORMAL' | 'ELEVATED' | 'WARNING' | 'HAZARD' | string;
  overall: 'COMFORTABLE_SAFE' | 'THERMALLY_UNCOMFORTABLE' | 'POOR_AIR_QUALITY' | string;
  warmed_up: boolean;
}

export interface AudioReading {
  label: string;
  title: string;
  confidence: number;
  db: number;
  method: string;
}

export interface Telemetry {
  v: number;
  robot_id: string;
  ts: number;
  state: RobotState;
  simulation: boolean;
  privacy_mode: boolean;
  battery: { voltage: number | null; percent: number | null };
  pose: { x: number; y: number; heading_deg: number; zone: string | null; odometer_m?: number };
  ultrasonic_cm: { left: number; center: number; right: number };
  imu?: { yaw_deg: number; pitch_deg: number; roll_deg: number };
  motors?: { left: number; right: number };
  environment: EnvironmentReading | null;
  audio: AudioReading | null;
  safety: {
    blocked: boolean;
    safe_hold: boolean;
    last_stop_latency_ms: number | null;
    cloud_silent_s: number;
    stop_distance_cm: number;
    stop_count?: number;
    max_loop_ms?: number;
  };
  pan_tilt?: { pan: number; tilt: number };
  faults?: string[];
  health?: Record<string, ComponentHealth>;
}

export interface ComponentHealth {
  ok: boolean;
  detail: string;
  hint: string;
}

export interface RobotInfo {
  simulation: boolean;
  simulator?: 'webots' | '2d' | null;
  zones: Record<string, { x: number; y: number; radius?: number }>;
  webrtc?: boolean;
  audio_model?: string;
  health?: Record<string, ComponentHealth>;
  software?: { version: string };
  safety?: { stop_distance_cm: number; cloud_timeout_s: number };
}

export interface ServerHealth {
  status: string;
  mqtt_connected: boolean;
  robots: Record<string, RobotSummary>;
  planner: string;
  vlm: string;
  stt: string;
  proctor?: ProctorInfo;
  warnings?: string[];
  version?: string;
  product?: string;
  site?: string;
  memory: { ready: boolean; backend: string | null; records: number; error: string | null };
}

export interface UserAccount {
  username: string;
  role: 'admin' | 'operator' | 'viewer';
  name: string;
  created: number;
  disabled: boolean;
  last_login: number | null;
}

export interface Schedule {
  id: string;
  name: string;
  command: string;
  time: string;
  days: number[];
  enabled: boolean;
  robot_id: string | null;
  created_by: string;
  last_run: number | null;
  last_status: string | null;
  last_report: string | null;
}

export interface RobotEvent {
  type: 'event';
  event: string;
  ts: number;
  data: Record<string, unknown>;
}

export interface RobotSummary {
  robot_id: string;
  online: boolean;
  state: RobotState | null;
  simulation: boolean | null;
  zone: string | null;
  zones: string[];
}

export interface AgentStep {
  tool: string;
  args: Record<string, unknown>;
  status: 'pending' | 'running' | 'done' | 'error';
  summary: string;
}

export interface ChatResponse {
  reply: string;
  steps: AgentStep[];
  report_id: string | null;
  planner: string;
  duration_s: number;
  speech: string;
  ack: string | null;
  images: string[];
}

export interface Anomaly {
  type: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  source: string;
}

export interface VisionAnalysis {
  occupants: number;
  lights_on: boolean;
  projector_on: boolean;
  monitors_on: boolean;
  hazardous_items: string[];
  exit_clear: boolean;
  extinguisher_present: boolean;
  description: string;
  confidence: number;
  provider: string;
  needs_human_review: boolean;
}

export interface ZoneInspection {
  id: string;
  zone: string;
  ts: number;
  vision: VisionAnalysis | null;
  environment: EnvironmentReading | null;
  audio: AudioReading | null;
  image_file: string | null;
  anomalies: Anomaly[];
  recommended_actions: { priority: string; category: string; action: string }[];
  energy_status: string;
  safety_status: string;
  comfort_verdict: string | null;
  gas_verdict: string | null;
  compliant: boolean;
  summary: string;
}

export interface InspectionReport {
  id: string;
  created: number;
  robot_id: string;
  request: string;
  zones: ZoneInspection[];
  title: string;
  markdown: string;
}

export interface ReportListItem {
  id: string;
  created: number;
  robot_id: string;
  request: string;
  zones: string[];
  compliant: boolean;
}

export interface SearchHit {
  id: string;
  text: string;
  score: number;
  metadata: Record<string, string | number | boolean>;
}

export interface SearchResponse {
  query: string;
  filters: Record<string, unknown>;
  results: SearchHit[];
  took_ms: number;
  embedding: string;
}

export type ServerMessage =
  | { kind: 'telemetry'; robot_id: string; data: Telemetry }
  | { kind: 'events'; robot_id: string; data: RobotEvent }
  | { kind: 'status'; robot_id: string; data: { online: boolean } }
  | { kind: 'info'; robot_id: string; data: RobotInfo }
  | { kind: 'agent'; robot_id: string; data: { type: string; [k: string]: any } }
  | { kind: 'pong'; ts: number };

export interface HistorySample {
  ts: number;
  temperature_c: number | null;
  humidity_pct: number | null;
  aqi: number | null;
  db: number | null;
  battery: number | null;
  x: number | null;
  y: number | null;
  zone: string | null;
}

export interface MapResponse {
  zones: Record<string, { x: number; y: number; radius?: number }>;
  map: { bounds?: number[] | null; obstacles?: number[][] };
  status: Record<string, { level: 'ok' | 'warn' | 'alert'; issues: number; report_id: string; ts: number; compliant: boolean }>;
  pose: { x: number; y: number; heading_deg: number; zone: string | null } | null;
}

export type FlagType = 'phone' | 'notes' | 'earpiece' | 'head_turn' | 'looking_down' | 'talking' | 'whisper' | 'noise';

export interface MonitorIncident {
  ts: number;
  type: FlagType;
  title: string;
  types?: FlagType[];
  db?: number | null;
  direction?: string | null;
  where?: string | null;
  detail?: string | null;
  image: string | null;
  close_image?: string | null;
  summary: string;
  warned: boolean;
  waypoint?: number | null;
}

export type DetectKey = 'head' | 'looking_down' | 'objects' | 'talking' | 'whisper' | 'noise';

export interface ExamSession {
  id: string;
  zone: string | null;
  started: number;
  ended?: number;
  minutes: number;
  mode: 'patrol' | 'stay';
  incident_count?: number;
  incidents?: MonitorIncident[];
  stop_reason?: string;
  vision?: string | null;
  views?: number;
}

export interface AiSettings {
  provider: 'none' | 'gemini' | 'openai' | 'ollama';
  vision_provider: string;
  stt_provider: string;
  google_api_key: string | null;
  openai_api_key: string | null;
  gemini_model: string;
  openai_model: string;
  ollama_base_url: string;
  ollama_model: string;
  ollama_vision_model: string;
  packages: Record<string, boolean>;
  help: Record<string, string>;
  active: { planner: string; vision: string; voice: string };
  saved?: boolean;
}

export interface ProctorInfo { mode: string; mediapipe: boolean; vision_ai: boolean; text: string }

export interface MonitorStatus {
  active: boolean;
  zone?: string | null;
  started?: number;
  ends_at?: number;
  minutes?: number;
  minutes_left?: number;
  sensitivity?: 'low' | 'normal' | 'high';
  phase?: string;
  level_db?: number | null;
  baseline_db?: number | null;
  incidents?: MonitorIncident[];
  stop_reason?: string;
  text?: string;
  id?: string;
  mode?: 'patrol' | 'stay';
  detect?: Record<DetectKey, boolean>;
  views?: number;
  rounds?: number;
  vision?: string | null;
  waypoint?: number | null;
  route?: number[][];
  view_pan?: number;
  view_dir?: number;
  students_seen?: number;
}
