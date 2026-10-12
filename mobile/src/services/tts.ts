// Spoken replies (text-to-speech). Phone: the OS voice via expo-speech. Web: the browser voice.
import * as Speech from 'expo-speech';

import { store } from '@/store';

let speaking = false;
const listeners = new Set<(on: boolean) => void>();

function set(on: boolean) {
  speaking = on;
  listeners.forEach((l) => l(on));
}

export const tts = {
  speak(text?: string | null) {
    const t = (text ?? '').trim();
    if (!t) return;
    Speech.stop();
    const rate = store.getState().session.speechRate ?? 1;
    Speech.speak(t.slice(0, 900), {
      language: 'en-US',
      rate,
      pitch: 1.0,
      onStart: () => set(true),
      onDone: () => set(false),
      onStopped: () => set(false),
      onError: () => set(false),
    });
    set(true);
  },
  stop() {
    Speech.stop();
    set(false);
  },
  get speaking() {
    return speaking;
  },
  subscribe(l: (on: boolean) => void) {
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  },
};
