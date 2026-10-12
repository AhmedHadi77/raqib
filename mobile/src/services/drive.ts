// Manual driving: keeps re-sending the current wheel command every 150 ms while a control is held.
// The robot's dead-man timer stops the wheels 0.6 s after the last command (e.g. if Wi-Fi drops).
import { store } from '@/store';

import { api } from './api';

let timer: ReturnType<typeof setInterval> | null = null;
let current: [number, number] = [0, 0];
let lastError: string | null = null;
const listeners = new Set<(v: [number, number], err: string | null) => void>();

function send(l: number, r: number) {
  const robotId = store.getState().session.robotId;
  api.command(robotId, 'drive', { left: +l.toFixed(2), right: +r.toFixed(2) }, false)
    .then(() => {
      if (lastError) {
        lastError = null;
        notify();
      }
    })
    .catch((e) => {
      lastError = e?.message ?? String(e);
      notify();
    });
}

function notify() {
  listeners.forEach((f) => f(current, lastError));
}

export const drive = {
  /** wheel powers in -1..1 */
  set(l: number, r: number) {
    const changed = Math.abs(l - current[0]) > 0.02 || Math.abs(r - current[1]) > 0.02;
    current = [l, r];
    if (l === 0 && r === 0) return drive.stop();
    if (changed || !timer) send(l, r);
    if (!timer) timer = setInterval(() => send(current[0], current[1]), 150);
    notify();
  },
  stop() {
    if (timer) clearInterval(timer);
    timer = null;
    current = [0, 0];
    send(0, 0);
    notify();
  },
  get active() {
    return !!timer;
  },
  subscribe(f: (v: [number, number], err: string | null) => void) {
    listeners.add(f);
    return () => {
      listeners.delete(f);
    };
  },
};

export type Dir = 'f' | 'b' | 'l' | 'r' | 'fl' | 'fr' | 'bl' | 'br';

export function dirToWheels(d: Dir, speed: number): [number, number] {
  const s = speed;
  switch (d) {
    case 'f': return [s, s];
    case 'b': return [-s, -s];
    case 'l': return [-0.8 * s, 0.8 * s];
    case 'r': return [0.8 * s, -0.8 * s];
    case 'fl': return [0.3 * s, s];
    case 'fr': return [s, 0.3 * s];
    case 'bl': return [-0.3 * s, -s];
    case 'br': return [-s, -0.3 * s];
  }
}
