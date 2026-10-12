import { store, sessionActions } from '@/store';
import type {
  AiSettings,
  ChatResponse,
  DetectKey,
  ExamSession,
  ProctorInfo,
  MonitorStatus,
  RobotInfo,
  Schedule,
  ServerHealth,
  Telemetry,
  UserAccount,
  HistorySample,
  MapResponse,
  InspectionReport,
  ReportListItem,
  RobotSummary,
  SearchResponse,
} from '@/types';

import { demoAsset, DemoError, demoRequest, demoText, isDemo } from '@/demo/demo';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function base() {
  return store.getState().session.serverUrl;
}

function token() {
  return store.getState().session.token;
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  if (isDemo(base())) {
    try {
      return (await demoRequest(path, init)) as T;
    } catch (e: any) {
      if (e instanceof DemoError) throw new ApiError(e.status, e.message);
      throw new ApiError(500, e?.message ?? String(e));
    }
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as any) };
    const t = token();
    if (t) headers.Authorization = `Bearer ${t}`;
    const res = await fetch(`${base()}${path}`, { ...init, headers, signal: ctrl.signal });
    if (res.status === 401) {
      store.dispatch(sessionActions.loggedOut());
      throw new ApiError(401, 'Session expired - please log in again');
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, body?.detail ?? `HTTP ${res.status}`);
    return body as T;
  } catch (e: any) {
    if (e?.name === 'AbortError') throw new ApiError(0, `Server did not answer (${base()})`);
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, `Cannot reach ${base()} - check Settings > Server URL. (${e?.message ?? e})`);
  } finally {
    clearTimeout(timer);
  }
}

/** URL with ?token= for <Image> sources and WebSockets (they cannot send headers everywhere). */
export function authUrl(path: string): string {
  if (isDemo(base())) return demoAsset(path);
  const sep = path.includes('?') ? '&' : '?';
  return `${base()}${path}${sep}token=${encodeURIComponent(token() ?? '')}`;
}

/** Fetch a text/HTML endpoint with the auth header (used for the printable report). */
async function requestText(path: string, timeoutMs = 30000): Promise<string> {
  if (isDemo(base())) return demoText(path);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const t = token();
    const res = await fetch(`${base()}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {}, signal: ctrl.signal });
    if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
    return await res.text();
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  reportHtml: (id: string) => requestText(`/reports/${id}/print`),
  health: () => request<ServerHealth>('/health', {}, 5000),
  login: (username: string, password: string) =>
    request<{ access_token: string; role: 'admin' | 'operator' | 'viewer'; username: string; name?: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  robots: () => request<RobotSummary[]>('/robots'),
  command: (robotId: string, action: string, params: Record<string, unknown> = {}, wait = true) =>
    request<any>(`/robots/${robotId}/command`, { method: 'POST', body: JSON.stringify({ action, params, wait }) }, 130000),
  history: (robotId: string, minutes = 15) => request<HistorySample[]>(`/robots/${robotId}/history?minutes=${minutes}`),
  map: (robotId: string) => request<MapResponse>(`/robots/${robotId}/map`),
  estop: (robotId: string) => request<any>(`/robots/${robotId}/estop`, { method: 'POST' }, 6000),
  reset: (robotId: string) => request<any>(`/robots/${robotId}/reset`, { method: 'POST' }),
  ping: (robotId: string) => request<{ median_ms: number | null }>(`/robots/${robotId}/ping`),
  chat: (message: string, robotId: string, opts: { source?: 'text' | 'voice'; zoneHint?: string | null } = {}) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, robot_id: robotId, source: opts.source ?? 'text', zone_hint: opts.zoneHint ?? null }),
    }, 600000),
  robot: (robotId: string) =>
    request<{ online: boolean; telemetry: Telemetry | null; info: RobotInfo | null }>(`/robots/${robotId}`),
  changePassword: (current_password: string, new_password: string) =>
    request<any>('/auth/password', { method: 'POST', body: JSON.stringify({ current_password, new_password }) }),
  users: () => request<UserAccount[]>('/users'),
  createUser: (u: { username: string; password: string; role: string; name?: string }) =>
    request<any>('/users', { method: 'POST', body: JSON.stringify(u) }),
  updateUser: (username: string, patch: { role?: string; name?: string; password?: string; disabled?: boolean }) =>
    request<any>(`/users/${encodeURIComponent(username)}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  deleteUser: (username: string) => request<any>(`/users/${encodeURIComponent(username)}`, { method: 'DELETE' }),
  monitor: () => request<MonitorStatus>('/monitor'),
  monitorStart: (zone: string | null, minutes: number, sensitivity: string, mode: 'patrol' | 'stay' = 'patrol',
    detect?: Partial<Record<DetectKey, boolean>>) =>
    request<MonitorStatus>('/monitor/start', { method: 'POST', body: JSON.stringify({ zone, minutes, sensitivity, mode, detect }) }, 30000),
  monitorSessions: () => request<ExamSession[]>('/monitor/sessions'),
  monitorSession: (id: string) => request<ExamSession>(`/monitor/sessions/${id}`),
  monitorHtml: (id: string) => requestText(`/monitor/sessions/${id}/print`),
  monitorCaps: () => request<ProctorInfo>('/monitor/capabilities'),
  aiSettings: () => request<AiSettings>('/admin/ai'),
  saveAiSettings: (body: Record<string, any>) => request<AiSettings>('/admin/ai', { method: 'PUT', body: JSON.stringify(body) }, 30000),
  testAi: () => request<{ ok: boolean; error?: string; seconds?: number; plan?: string | null; reply?: string | null; sample?: string; model?: string }>(
    '/admin/ai/test', { method: 'POST' }, 60000),
  monitorStop: () => request<{ text: string }>('/monitor/stop', { method: 'POST' }, 20000),
  schedules: () => request<Schedule[]>('/schedules'),
  saveSchedule: (s: Partial<Schedule> & { name: string; command: string; time: string; days: number[] }) =>
    request<Schedule>('/schedules', { method: 'POST', body: JSON.stringify(s) }),
  enableSchedule: (id: string, enabled: boolean) =>
    request<any>(`/schedules/${id}/enabled?enabled=${enabled}`, { method: 'POST' }),
  deleteSchedule: (id: string) => request<any>(`/schedules/${id}`, { method: 'DELETE' }),
  runSchedule: (id: string) => request<any>(`/schedules/${id}/run`, { method: 'POST' }),
  /** Upload a voice recording; returns the recognised text. */
  transcribe: async (uri: string, mime = 'audio/m4a'): Promise<{ text: string; provider: string; ms: number }> => {
    if (isDemo(base())) throw new ApiError(503, 'Voice needs the real robot. In the demo, type your command instead.');
    const form = new FormData();
    if (uri.startsWith('blob:') || uri.startsWith('data:')) {
      const blob = await (await fetch(uri)).blob();
      form.append('file', blob, mime.includes('webm') ? 'voice.webm' : 'voice.m4a');
    } else {
      form.append('file', { uri, name: 'voice.m4a', type: mime } as any);
    }
    const t = token();
    const res = await fetch(`${base()}/voice/transcribe`, {
      method: 'POST',
      body: form,
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(res.status, body?.detail ?? `HTTP ${res.status}`);
    return body;
  },
  reports: () => request<ReportListItem[]>('/reports'),
  report: (id: string) => request<InspectionReport>(`/reports/${id}`),
  search: (q: string, days?: number) =>
    request<SearchResponse>(`/search?q=${encodeURIComponent(q)}${days ? `&days=${days}` : ''}&k=10`),
  seed: () => request<any>('/memory/seed?n=60', { method: 'POST' }, 60000),
  webrtcOffer: (sdp: string, type: string, robotId: string) =>
    request<{ sdp: string; type: string }>('/webrtc/offer', {
      method: 'POST',
      body: JSON.stringify({ sdp, type, robot_id: robotId }),
    }, 25000),
};
