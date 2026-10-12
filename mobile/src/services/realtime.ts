// WebSocket to the backend: live telemetry, robot events and agent progress.
// (The app talks to the backend, never directly to the MQTT broker, so broker
//  credentials never leave the server.)
import { chatActions, robotActions, store } from '@/store';
import type { ServerMessage } from '@/types';

import { demoConnect, isDemo } from '@/demo/demo';

import { handleRobotEvent } from './alerts';
import { speakAck } from './assistant';

let ws: WebSocket | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let pingTimer: ReturnType<typeof setInterval> | null = null;
let stopped = true;
let demoOff: (() => void) | null = null;

function wsUrl() {
  const { serverUrl, token } = store.getState().session;
  return `${serverUrl.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(token ?? '')}`;
}

function handle(msg: ServerMessage) {
  const robotId = store.getState().session.robotId;
  if ('robot_id' in msg && msg.robot_id !== robotId) return;
  switch (msg.kind) {
    case 'telemetry':
      store.dispatch(robotActions.telemetry(msg.data));
      break;
    case 'status':
      store.dispatch(robotActions.online(msg.data.online));
      break;
    case 'info':
      store.dispatch(robotActions.info(msg.data));
      break;
    case 'events':
      store.dispatch(robotActions.event(msg.data));
      handleRobotEvent(msg.data);
      break;
    case 'agent': {
      const d = msg.data;
      if (d.type === 'plan') {
        store.dispatch(chatActions.plan(d.steps));
        speakAck(d.ack);
      }
      else if (d.type === 'step') store.dispatch(chatActions.step({ index: d.index, step: d.step }));
      else if (d.type === 'progress' && d.summary) store.dispatch(chatActions.progress(d.summary));
      break;
    }
  }
}

function connect() {
  if (stopped) return;
  if (isDemo(store.getState().session.serverUrl)) {
    demoOff = demoConnect(handle);
    store.dispatch(robotActions.wsStatus(true));
    return;
  }
  try {
    ws = new WebSocket(wsUrl());
  } catch {
    schedule();
    return;
  }
  ws.onopen = () => {
    store.dispatch(robotActions.wsStatus(true));
    pingTimer = setInterval(() => ws?.readyState === 1 && ws.send(JSON.stringify({ type: 'ping' })), 20000);
  };
  ws.onmessage = (ev) => {
    try {
      handle(JSON.parse(String(ev.data)));
    } catch {
      /* ignore malformed */
    }
  };
  ws.onclose = () => {
    store.dispatch(robotActions.wsStatus(false));
    if (pingTimer) clearInterval(pingTimer);
    schedule();
  };
  ws.onerror = () => ws?.close();
}

function schedule() {
  if (stopped || retryTimer) return;
  retryTimer = setTimeout(() => {
    retryTimer = null;
    connect();
  }, 3000);
}

export const realtime = {
  start() {
    if (!stopped) return;
    stopped = false;
    connect();
  },
  stop() {
    stopped = true;
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = null;
    ws?.close();
    ws = null;
    demoOff?.();
    demoOff = null;
  },
  restart() {
    this.stop();
    this.start();
  },
};
