// One entry point for talking to the robot's AI agent (typed, tapped or spoken).
import { chatActions, store } from '@/store';

import { api } from './api';
import { tts } from './tts';

export async function ask(text: string, opts: { voice?: boolean; zoneHint?: string | null } = {}) {
  const msg = text.trim();
  const { chat, session } = store.getState();
  if (!msg || chat.busy) return null;
  tts.stop();
  store.dispatch(chatActions.userSaid({ text: msg, voice: opts.voice }));
  try {
    const r = await api.chat(msg, session.robotId, { source: opts.voice ? 'voice' : 'text', zoneHint: opts.zoneHint });
    store.dispatch(chatActions.agentReplied(r));
    if (opts.voice || store.getState().session.autoSpeak) tts.speak(r.speech || r.reply);
    return r;
  } catch (e: any) {
    const m = e?.message ?? String(e);
    store.dispatch(chatActions.failed(m));
    if (opts.voice) tts.speak(`Sorry, that didn't work. ${m}`);
    return null;
  }
}

/** Called when the agent has planned a mission: say what it is about to do. */
export function speakAck(ack?: string | null) {
  const { chat, session } = store.getState();
  if (ack && chat.busy && (chat.voiceTurn || session.autoSpeak)) tts.speak(ack);
}
