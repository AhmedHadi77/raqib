import { configureStore, createSlice, PayloadAction } from '@reduxjs/toolkit';
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';

import type { AgentStep, ChatResponse, RobotEvent, RobotInfo, Telemetry } from '@/types';

export type Role = 'admin' | 'operator' | 'viewer';
export type ThemeMode = 'system' | 'light' | 'dark';

// ------------------------------------------------------------------ settings + auth
interface SessionState {
  hydrated: boolean;
  serverUrl: string;
  robotId: string;
  token: string | null;
  username: string | null;
  name: string | null;
  role: Role | null;
  notifications: boolean;
  autoSpeak: boolean;      // read assistant replies aloud
  speechRate: number;      // 0.8 .. 1.2
  themeMode: ThemeMode;
  driveSpeed: number;      // 0.35 | 0.6 | 0.9
}

const initialSession: SessionState = {
  hydrated: false,
  serverUrl: 'http://192.168.1.100:8000',
  robotId: 'robot01',
  token: null,
  username: null,
  name: null,
  role: null,
  notifications: true,
  autoSpeak: true,
  speechRate: 1.0,
  themeMode: 'system',
  driveSpeed: 0.6,
};

export const PERSISTED: (keyof SessionState)[] = [
  'serverUrl', 'robotId', 'token', 'username', 'name', 'role', 'notifications', 'autoSpeak', 'speechRate',
  'themeMode', 'driveSpeed',
];

const session = createSlice({
  name: 'session',
  initialState: initialSession,
  reducers: {
    hydrate: (s, a: PayloadAction<Partial<SessionState>>) => ({ ...s, ...a.payload, hydrated: true }),
    setServer: (s, a: PayloadAction<{ serverUrl: string; robotId?: string }>) => {
      s.serverUrl = a.payload.serverUrl.replace(/\/+$/, '');
      if (a.payload.robotId) s.robotId = a.payload.robotId;
    },
    loggedIn: (s, a: PayloadAction<{ token: string; username: string; role: Role; name?: string | null }>) => {
      s.token = a.payload.token;
      s.username = a.payload.username;
      s.role = a.payload.role;
      s.name = a.payload.name ?? a.payload.username;
    },
    setPrefs: (s, a: PayloadAction<Partial<Pick<SessionState, 'notifications' | 'autoSpeak' | 'speechRate' | 'themeMode' | 'driveSpeed'>>>) => ({
      ...s,
      ...a.payload,
    }),
    setNotifications: (s, a: PayloadAction<boolean>) => {
      s.notifications = a.payload;
    },
    loggedOut: (s) => {
      s.token = null;
      s.username = null;
      s.role = null;
      s.name = null;
    },
  },
});

// ------------------------------------------------------------------ live robot data
interface RobotLiveState {
  wsConnected: boolean;
  online: boolean;
  telemetry: Telemetry | null;
  info: RobotInfo | null;
  zones: string[];
  simulation: boolean | null;
  events: RobotEvent[];
}

const robot = createSlice({
  name: 'robot',
  initialState: { wsConnected: false, online: false, telemetry: null, info: null, zones: [], simulation: null, events: [] } as RobotLiveState,
  reducers: {
    wsStatus: (s, a: PayloadAction<boolean>) => {
      s.wsConnected = a.payload;
    },
    telemetry: (s, a: PayloadAction<Telemetry>) => {
      s.telemetry = a.payload;
      s.online = true;
      s.simulation = a.payload.simulation;
    },
    online: (s, a: PayloadAction<boolean>) => {
      s.online = a.payload;
    },
    info: (s, a: PayloadAction<RobotInfo>) => {
      s.info = a.payload;
      s.zones = Object.keys(a.payload.zones ?? {});
    },
    zones: (s, a: PayloadAction<string[]>) => {
      s.zones = a.payload;
    },
    event: (s, a: PayloadAction<RobotEvent>) => {
      s.events = [a.payload, ...s.events].slice(0, 60);
    },
  },
});

// ------------------------------------------------------------------ chat
export interface ChatMessage {
  id: string;
  from: 'user' | 'agent' | 'system';
  text: string;
  ts: number;
  steps?: AgentStep[];
  reportId?: string | null;
  planner?: string;
  duration?: number;
  speech?: string;
  voice?: boolean;
}

const chat = createSlice({
  name: 'chat',
  initialState: {
    messages: [] as ChatMessage[],
    busy: false,
    liveSteps: [] as AgentStep[],
    progress: '',
    voiceTurn: false,     // the current request came from the microphone
  },
  reducers: {
    userSaid: (s, a: PayloadAction<{ text: string; voice?: boolean }>) => {
      s.messages.push({ id: `u${Date.now()}`, from: 'user', text: a.payload.text, ts: Date.now(), voice: a.payload.voice });
      s.busy = true;
      s.liveSteps = [];
      s.progress = 'Planning…';
      s.voiceTurn = !!a.payload.voice;
    },
    plan: (s, a: PayloadAction<AgentStep[]>) => {
      s.liveSteps = a.payload;
    },
    step: (s, a: PayloadAction<{ index: number; step: AgentStep }>) => {
      s.liveSteps[a.payload.index] = a.payload.step;
      s.progress = a.payload.step.summary || `${a.payload.step.tool}…`;
    },
    progress: (s, a: PayloadAction<string>) => {
      s.progress = a.payload;
    },
    agentReplied: (s, a: PayloadAction<ChatResponse>) => {
      s.messages.push({
        id: `a${Date.now()}`,
        from: 'agent',
        text: a.payload.reply,
        ts: Date.now(),
        steps: a.payload.steps,
        reportId: a.payload.report_id,
        planner: a.payload.planner,
        duration: a.payload.duration_s,
        speech: a.payload.speech,
      });
      s.busy = false;
      s.liveSteps = [];
      s.progress = '';
    },
    failed: (s, a: PayloadAction<string>) => {
      s.messages.push({ id: `e${Date.now()}`, from: 'system', text: a.payload, ts: Date.now() });
      s.busy = false;
      s.progress = '';
    },
    clear: (s) => {
      s.messages = [];
    },
  },
});

// ------------------------------------------------------------------ alerts (in-app banner)
export interface AppAlert {
  id: string;
  title: string;
  body: string;
  level: 'warn' | 'alert' | 'ok';
  ts: number;
  reportId?: string;
  route?: string;
}

const alerts = createSlice({
  name: 'alerts',
  initialState: { items: [] as AppAlert[], log: [] as AppAlert[] },
  reducers: {
    push: (s, a: PayloadAction<AppAlert>) => {
      s.items = [a.payload, ...s.items].slice(0, 5);
      s.log = [a.payload, ...s.log].slice(0, 50);
    },
    dismiss: (s, a: PayloadAction<string>) => {
      s.items = s.items.filter((x) => x.id !== a.payload);
    },
  },
});

export const store = configureStore({
  reducer: { session: session.reducer, robot: robot.reducer, chat: chat.reducer, alerts: alerts.reducer },
});
export const alertActions = alerts.actions;

export const sessionActions = session.actions;
export const robotActions = robot.actions;
export const chatActions = chat.actions;

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
