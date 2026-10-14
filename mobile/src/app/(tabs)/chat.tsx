// Assistant: talk or type to the robot. Replies are shown here and read aloud.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { ActivityIndicator } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import EStopButton from '@/components/EStopButton';
import Markdown from '@/components/Markdown';
import { Body, Chip, IconBtn, Logo } from '@/components/ui';
import VoiceButton from '@/components/VoiceButton';
import { usePalette } from '@/hooks';
import { ask } from '@/services/assistant';
import { tts } from '@/services/tts';
import { ChatMessage, chatActions, sessionActions, useAppDispatch, useAppSelector } from '@/store';
import { fonts, ZONE_LABEL } from '@/theme';
import type { AgentStep } from '@/types';

const SUGGESTIONS: { label: string; icon: any; text: string }[] = [
  { label: 'What do you see?', icon: 'eye-outline', text: 'What do you see in front of you?' },
  { label: 'Check the aircon in Hall B', icon: 'air-conditioner', text: 'Check the aircon in Lecture Hall B' },
  { label: 'Go 2 m and take a photo', icon: 'camera-outline', text: 'Go forward 2 meters, take a picture and tell me what it is' },
  { label: 'Who is talking?', icon: 'account-voice', text: 'Who is talking? Tell them to stop talking' },
  { label: 'Monitor the exam', icon: 'shield-account-outline', text: 'Monitor the exam in Exam Hall for 60 minutes' },
  { label: 'Inspect IoT Lab and Hall B', icon: 'clipboard-check-outline', text: 'Inspect the IoT Lab and Lecture Hall B, then return home' },
  { label: 'What did you find?', icon: 'text-box-search-outline', text: 'What did you find?' },
  { label: 'Patrol all rooms', icon: 'map-marker-path', text: 'Patrol all rooms and return home' },
  { label: 'Unhealthy air last month', icon: 'history', text: 'Show me rooms where the air quality was unhealthy last month' },
];

const TOOL_LABEL: Record<string, string> = {
  inspect_zone: 'Inspect',
  go_to_zone: 'Drive to',
  return_home: 'Return to dock',
  move: 'Move',
  turn: 'Turn',
  stop: 'Stop',
  pan_tilt: 'Look around',
  capture_and_analyze: 'Look with the camera',
  read_environment: 'Read air and climate',
  listen_audio: 'Listen',
  search_history: 'Search past inspections',
  get_status: 'Check status',
  speak: 'Speak',
  check_ac: 'Check air-conditioning',
  last_findings: 'Recall latest results',
  find_sound: 'Find who is talking',
  start_monitoring: 'Start exam monitoring',
  stop_monitoring: 'Stop exam monitoring',
  monitor_status: 'Check the exam',
};

function stepTitle(s: AgentStep) {
  const a: any = s.args ?? {};
  const base = TOOL_LABEL[s.tool] ?? s.tool;
  if (a.zone) return `${base}${s.tool === 'check_ac' || s.tool === 'start_monitoring' ? ' in' : ''} ${ZONE_LABEL(a.zone)}`;
  if (a.distance_m != null) return `${base} ${a.distance_m > 0 ? 'forward' : 'back'} ${Math.abs(a.distance_m * 100).toFixed(0)} cm`;
  if (a.angle_deg != null) return `${base} ${a.angle_deg > 0 ? 'left' : 'right'} ${Math.abs(a.angle_deg)}°`;
  return base;
}

function Steps({ steps }: { steps: AgentStep[] }) {
  const p = usePalette();
  return (
    <View style={{ marginTop: 8 }}>
      {steps.map((s, i) => {
        const color = s.status === 'done' ? p.ok : s.status === 'error' ? p.danger : s.status === 'running' ? p.primary : p.line;
        const icon = s.status === 'done' ? 'check' : s.status === 'error' ? 'close' : s.status === 'running' ? 'dots-horizontal' : 'circle-small';
        return (
          <View key={i} style={styles.step}>
            <View style={{ alignItems: 'center' }}>
              <View style={[styles.stepDot, { borderColor: color, backgroundColor: s.status === 'pending' ? 'transparent' : color }]}>
                <MaterialCommunityIcons name={icon as any} size={12} color={s.status === 'pending' ? p.inkSoft : p.surface} />
              </View>
              {i < steps.length - 1 ? <View style={[styles.stepLine, { backgroundColor: p.line }]} /> : null}
            </View>
            <View style={{ flex: 1, paddingBottom: 10 }}>
              <Text style={{ fontFamily: fonts.bodyStrong, color: p.ink, fontSize: 14 }}>{stepTitle(s)}</Text>
              {s.summary && s.status !== 'done' ? <Body small soft numberOfLines={3}>{s.summary}</Body> : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

function Bubble({ m }: { m: ChatMessage }) {
  const p = usePalette();
  const [open, setOpen] = useState(false);
  if (m.from === 'user')
    return (
      <View style={[styles.user, { backgroundColor: p.ink }]}>
        {m.voice ? <MaterialCommunityIcons name="microphone" size={14} color={p.paper} style={{ marginTop: 3, opacity: 0.7 }} /> : null}
        <Text style={{ color: p.paper, fontFamily: fonts.bodyMedium, fontSize: 15, lineHeight: 21, flexShrink: 1 }}>{m.text}</Text>
      </View>
    );
  const sys = m.from === 'system';
  return (
    <View style={styles.agentRow}>
      <View style={{ marginTop: 2 }}><Logo size={26} /></View>
      <View style={[styles.agent, { backgroundColor: sys ? p.dangerSoft : p.surface, borderColor: sys ? p.dangerSoft : p.line }]}>
        <Markdown text={m.text} />
        <View style={styles.foot}>
          {m.reportId ? (
            <Pressable onPress={() => router.push(`/report/${m.reportId}`)} style={[styles.footBtn, { backgroundColor: p.primary }]}>
              <MaterialCommunityIcons name="file-document-outline" size={15} color={p.onPrimary} />
              <Text style={{ color: p.onPrimary, fontFamily: fonts.bodyStrong, fontSize: 13 }}>Open report</Text>
            </Pressable>
          ) : null}
          {!sys && (m.speech || m.text) ? (
            <Pressable onPress={() => tts.speak(m.speech || m.text)} style={[styles.footBtn, { backgroundColor: p.sunken }]} accessibilityLabel="Read aloud">
              <MaterialCommunityIcons name="volume-high" size={15} color={p.ink} />
              <Text style={{ color: p.ink, fontFamily: fonts.bodyStrong, fontSize: 13 }}>Listen</Text>
            </Pressable>
          ) : null}
          {m.steps?.length ? (
            <Pressable onPress={() => setOpen(!open)} style={[styles.footBtn, { backgroundColor: p.sunken }]}>
              <Text style={{ color: p.ink, fontFamily: fonts.bodyStrong, fontSize: 13 }}>
                {open ? 'Hide steps' : `${m.steps.length} step${m.steps.length > 1 ? 's' : ''}`}
              </Text>
            </Pressable>
          ) : null}
          {m.duration && m.duration > 1 ? <Body small soft style={{ marginLeft: 'auto' }}>{m.duration.toFixed(0)} s</Body> : null}
        </View>
        {open && m.steps ? <Steps steps={m.steps} /> : null}
      </View>
    </View>
  );
}

export default function Assistant() {
  const p = usePalette();
  const dispatch = useAppDispatch();
  const { messages, busy, liveSteps, progress } = useAppSelector((s) => s.chat);
  const { role, autoSpeak, name } = useAppSelector((s) => s.session);
  const [text, setText] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const list = useRef<FlatList<ChatMessage>>(null);
  const canCommand = role === 'operator' || role === 'admin';

  useEffect(() => tts.subscribe(setSpeaking), []);
  useEffect(() => {
    setTimeout(() => list.current?.scrollToEnd({ animated: true }), 120);
  }, [messages.length, liveSteps.length, progress]);

  const send = (msg?: string) => {
    const m = (msg ?? text).trim();
    if (!m || busy) return;
    setText('');
    ask(m);
  };

  const empty = (
    <View style={styles.empty}>
      <Logo size={64} />
      <Text style={[styles.hello, { color: p.ink }]}>Hi{name ? ` ${name}` : ''}. What should I check?</Text>
      <Body soft style={{ textAlign: 'center', maxWidth: 360 }}>
        Tap the microphone and speak, or type. I plan the route, drive there, look, listen and measure, then tell you what I found.
      </Body>
      <View style={styles.sugGrid}>
        {SUGGESTIONS.slice(0, 6).map((s) => (
          <Pressable key={s.label} disabled={!canCommand} onPress={() => send(s.text)}
            style={({ pressed }) => [styles.sug, { backgroundColor: pressed ? p.primarySoft : p.surface, borderColor: p.line, opacity: canCommand ? 1 : 0.5 }]}>
            <MaterialCommunityIcons name={s.icon} size={20} color={p.primary} />
            <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 14, color: p.ink, flex: 1 }}>{s.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: p.paper }}>
      <View style={styles.header}>
        <Text style={{ fontFamily: fonts.display, fontSize: 24, color: p.ink, letterSpacing: -0.5, flex: 1 }}>Assistant</Text>
        {speaking ? <IconBtn icon="stop-circle-outline" label="Stop reading" onPress={() => tts.stop()} /> : null}
        <IconBtn icon={autoSpeak ? 'volume-high' : 'volume-off'} label={autoSpeak ? 'Replies are read aloud' : 'Replies are silent'}
          onPress={() => { if (autoSpeak) tts.stop(); dispatch(sessionActions.setPrefs({ autoSpeak: !autoSpeak })); }}
          bg={autoSpeak ? p.primarySoft : undefined} color={autoSpeak ? p.primary : p.inkSoft} />
        {messages.length ? <IconBtn icon="broom" label="Clear conversation" onPress={() => dispatch(chatActions.clear())} /> : null}
      </View>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        <FlatList
          ref={list}
          data={messages}
          keyExtractor={(m) => m.id}
          renderItem={({ item }) => <Bubble m={item} />}
          contentContainerStyle={styles.list}
          ListEmptyComponent={empty}
          ListFooterComponent={
            busy ? (
              <View style={styles.agentRow}>
                <View style={{ marginTop: 2 }}><Logo size={26} /></View>
                <View style={[styles.agent, { backgroundColor: p.surface, borderColor: p.primary }]}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <ActivityIndicator size="small" color={p.primary} />
                    <Text style={{ fontFamily: fonts.bodyStrong, color: p.ink, flex: 1 }}>{progress || 'Planning…'}</Text>
                  </View>
                  {liveSteps.length ? <Steps steps={liveSteps} /> : null}
                  <View style={{ marginTop: 10, alignSelf: 'flex-start' }}><EStopButton compact /></View>
                </View>
              </View>
            ) : null
          }
        />
        {!busy && canCommand && messages.length ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }} contentContainerStyle={styles.chips}>
            {SUGGESTIONS.map((s) => <Chip key={s.label} icon={s.icon} label={s.label} onPress={() => send(s.text)} />)}
          </ScrollView>
        ) : null}
        <View style={[styles.composer, { backgroundColor: p.surface, borderTopColor: p.line }]}>
          <View style={[styles.inputWrap, { backgroundColor: p.sunken }]}>
            <TextInput
              style={[styles.input, { color: p.ink }]}
              placeholder={canCommand ? 'Type a command…' : 'Viewer accounts are read-only'}
              placeholderTextColor={p.inkFaint}
              value={text} onChangeText={setText} onSubmitEditing={() => send()} editable={canCommand && !busy}
              returnKeyType="send"
            />
            {text.trim() ? (
              <Pressable onPress={() => send()} disabled={busy} accessibilityLabel="Send"
                style={[styles.send, { backgroundColor: p.primary }]}>
                <MaterialCommunityIcons name="arrow-up" size={20} color={p.onPrimary} />
              </Pressable>
            ) : null}
          </View>
          <VoiceButton size={50} disabled={!canCommand} panelOffset={86} showProgress={false} />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6 },
  list: { padding: 14, gap: 14, maxWidth: 780, width: '100%', alignSelf: 'center', flexGrow: 1 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, paddingVertical: 24 },
  hello: { fontFamily: fonts.display, fontSize: 24, letterSpacing: -0.5, textAlign: 'center', marginTop: 8 },
  sugGrid: { width: '100%', maxWidth: 520, flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 14 },
  sug: { flexBasis: '47%', flexGrow: 1, flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: StyleSheet.hairlineWidth, borderRadius: 14, padding: 12 },
  user: { alignSelf: 'flex-end', maxWidth: '84%', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18, borderBottomRightRadius: 6, flexDirection: 'row', gap: 6 },
  agentRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', maxWidth: '96%' },
  agent: { flexShrink: 1, padding: 14, borderRadius: 18, borderTopLeftRadius: 6, borderWidth: StyleSheet.hairlineWidth },
  foot: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 10 },
  footBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 11, paddingVertical: 6, borderRadius: 999 },
  step: { flexDirection: 'row', gap: 10 },
  stepDot: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  stepLine: { width: 2, flex: 1, marginVertical: 2 },
  chips: { gap: 8, paddingHorizontal: 14, paddingVertical: 8 },
  composer: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 10, borderTopWidth: StyleSheet.hairlineWidth },
  inputWrap: { flex: 1, flexDirection: 'row', alignItems: 'center', borderRadius: 24, paddingLeft: 16, paddingRight: 5, minHeight: 48 },
  input: { flex: 1, fontFamily: fonts.body, fontSize: 15.5, paddingVertical: 10, outlineStyle: 'none' as any },
  send: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
});
