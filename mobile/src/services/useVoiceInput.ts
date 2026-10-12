// Push-to-talk speech input.
//  * Web (Chrome / Edge on https or localhost): the browser's own speech recognition - instant, live transcript.
//  * Phone app (and other browsers): records with the microphone, then the server transcribes it
//    (faster-whisper offline, or Whisper / Gemini with an API key).
// Recording stops by itself after ~1.3 s of silence once you have spoken, or after 15 s.
import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';

import { api } from './api';
import { tts } from './tts';

export type VoiceState = 'idle' | 'listening' | 'transcribing';

const SpeechRec: any =
  Platform.OS === 'web' && typeof window !== 'undefined'
    ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    : null;
const secureWeb = Platform.OS !== 'web' || (typeof window !== 'undefined' && (window as any).isSecureContext);

const OPTIONS = { ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true };

export function useVoiceInput(onText: (text: string) => void) {
  const [state, setState] = useState<VoiceState>('idle');
  const [partial, setPartial] = useState('');
  const [error, setError] = useState<string | null>(null);
  const recorder = useAudioRecorder(OPTIONS);
  const rs = useAudioRecorderState(recorder, 120);
  const rec = useRef<any>(null);
  const finalText = useRef('');
  const heard = useRef(false);
  const quietSince = useRef<number | null>(null);
  const startedAt = useRef(0);
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const mode: 'browser' | 'record' | 'none' = SpeechRec && secureWeb ? 'browser' : secureWeb ? 'record' : 'none';
  // metering in dBFS: -160 (silence) .. 0 (loud)
  const level = state === 'listening' && mode === 'record' ? Math.max(0, Math.min(1, ((rs.metering ?? -60) + 55) / 45)) : 0;

  const finishRecording = useCallback(async () => {
    if (state !== 'listening' || mode !== 'record') return;
    setState('transcribing');
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error('nothing was recorded');
      const mime = Platform.OS === 'web' ? 'audio/webm' : 'audio/m4a';
      const r = await api.transcribe(uri, mime);
      setState('idle');
      if (r.text) onTextRef.current(r.text);
      else setError("I didn't catch that - try again a little closer to the phone.");
    } catch (e: any) {
      setState('idle');
      setError(e?.message ?? String(e));
    }
  }, [state, mode, recorder]);

  // silence detection while recording
  useEffect(() => {
    if (state !== 'listening' || mode !== 'record') return;
    const now = Date.now();
    const db = rs.metering ?? -160;
    if (db > -38) {
      heard.current = true;
      quietSince.current = null;
    } else if (heard.current) {
      quietSince.current ??= now;
      if (now - quietSince.current > 1300) finishRecording();
    }
    if (now - startedAt.current > 15000) finishRecording();
  }, [rs.metering, rs.durationMillis, state, mode, finishRecording]);

  const start = useCallback(async () => {
    setError(null);
    setPartial('');
    tts.stop();
    if (mode === 'none') {
      setError('The microphone only works in the app or on a secure (https) page. Type your command instead.');
      return;
    }
    if (mode === 'browser') {
      const r = new SpeechRec();
      r.lang = 'en-US';
      r.interimResults = true;
      r.continuous = false;
      r.maxAlternatives = 1;
      finalText.current = '';
      r.onresult = (ev: any) => {
        let interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const t = ev.results[i][0].transcript;
          if (ev.results[i].isFinal) finalText.current += t;
          else interim += t;
        }
        setPartial((finalText.current + ' ' + interim).trim());
      };
      r.onerror = (ev: any) => {
        if (ev.error === 'not-allowed') setError('Allow the microphone for this site to talk to the robot.');
        else if (ev.error !== 'no-speech' && ev.error !== 'aborted') setError(`Speech recognition: ${ev.error}`);
      };
      r.onend = () => {
        rec.current = null;
        setState('idle');
        const t = finalText.current.trim();
        if (t) onTextRef.current(t);
      };
      rec.current = r;
      r.start();
      setState('listening');
      return;
    }
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) {
      setError('Allow microphone access in your phone settings to use voice commands.');
      return;
    }
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync(OPTIONS);
    heard.current = false;
    quietSince.current = null;
    startedAt.current = Date.now();
    recorder.record();
    setState('listening');
  }, [mode, recorder]);

  const stop = useCallback(() => {
    if (mode === 'browser') rec.current?.stop();
    else finishRecording();
  }, [mode, finishRecording]);

  const cancel = useCallback(async () => {
    if (mode === 'browser') {
      finalText.current = '';
      rec.current?.abort();
    } else if (state === 'listening') {
      try {
        await recorder.stop();
      } catch {
        /* already stopped */
      }
    }
    setState('idle');
  }, [mode, state, recorder]);

  useEffect(() => {
    if (state === 'idle' && Platform.OS !== 'web') {
      setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true }).catch(() => {});
    }
  }, [state]);

  return { state, partial, error, level, start, stop, cancel, mode, clearError: () => setError(null) };
}
