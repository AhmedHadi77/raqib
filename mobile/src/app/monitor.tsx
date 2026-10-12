// Exam monitor: the robot patrols the exam room, looks all the way round and listens. It flags phones,
// notes, earpieces, heads turned to a neighbour's paper, looking down too long, talking, whispering and
// sudden noises, tells the student to stop and sends a photo here. It never identifies anyone.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import React, { useMemo, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { Button, Snackbar } from 'react-native-paper';
import Svg, { Circle, Path } from 'react-native-svg';

import { Body, Card, Chip, Divider, EmptyState, ListRow, Pill, Screen, Section, Segmented, Sheet } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { api, authUrl } from '@/services/api';
import { exportHtmlAsPdf } from '@/services/pdf';
import { useAppSelector } from '@/store';
import { fonts, ZONE_LABEL } from '@/theme';
import type { DetectKey, ExamSession, FlagType, MonitorIncident } from '@/types';

type IconName = React.ComponentProps<typeof MaterialCommunityIcons>['name'];

const PHASE: Record<string, string> = {
  starting: 'Starting',
  driving: 'Driving to the room',
  calibrating: 'Learning how quiet the room is',
  patrolling: 'Walking to the next spot',
  watching: 'Watching the students',
  listening: 'Listening',
  responding: 'Dealing with an incident',
  returning: 'Going back to its route',
  finished: 'Finished',
};

export const FLAG_ICON: Record<FlagType, IconName> = {
  phone: 'cellphone',
  notes: 'file-document-outline',
  earpiece: 'headphones',
  head_turn: 'eye-outline',
  looking_down: 'arrow-down-circle-outline',
  talking: 'account-voice',
  whisper: 'ear-hearing',
  noise: 'volume-high',
};
const VISUAL: FlagType[] = ['phone', 'notes', 'earpiece', 'head_turn', 'looking_down'];

const CHECKS: { key: DetectKey; label: string; icon: IconName; note: string }[] = [
  { key: 'objects', label: 'Phones, notes, earpieces', icon: 'cellphone', note: 'Seen in the camera' },
  { key: 'head', label: 'Head turned', icon: 'eye-outline', note: 'Looking at another paper for 3 s' },
  { key: 'looking_down', label: 'Looking down', icon: 'arrow-down-circle-outline', note: 'Head bowed to the lap for 8 s' },
  { key: 'talking', label: 'Talking', icon: 'account-voice', note: 'Finds the voice and goes there' },
  { key: 'whisper', label: 'Whispering', icon: 'ear-hearing', note: 'Quiet voices near the robot' },
  { key: 'noise', label: 'Sudden noises', icon: 'volume-high', note: 'Photo of where it happened' },
];

const hhmm = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

/** Small 360 degree dial: which way the camera is looking right now. */
function ViewDial({ dir, size = 54 }: { dir?: number | null; size?: number }) {
  const r = size / 2 - 3;
  const c = size / 2;
  const a = (((dir ?? 0) + 90) * Math.PI) / 180;           // 0 = straight ahead = up
  const span = (31 * Math.PI) / 180;
  const p1 = [c + r * Math.cos(Math.PI * 2 - a - span), c - r * Math.sin(Math.PI * 2 - a - span)];
  const p2 = [c + r * Math.cos(Math.PI * 2 - a + span), c - r * Math.sin(Math.PI * 2 - a + span)];
  return (
    <Svg width={size} height={size}>
      <Circle cx={c} cy={c} r={r} stroke="#3A4A78" strokeWidth={2} fill="none" />
      {dir != null ? (
        <Path d={`M${c},${c} L${p1[0]},${p1[1]} A${r},${r} 0 0 0 ${p2[0]},${p2[1]} Z`} fill="#1FC8E3" opacity={0.75} />
      ) : null}
      <Circle cx={c} cy={c} r={4} fill="#EEF2FF" />
    </Svg>
  );
}

function IncidentCard({ i }: { i: MonitorIncident }) {
  const p = usePalette();
  const [close, setClose] = useState(false);
  const img = close && i.close_image ? i.close_image : i.image;
  const visual = VISUAL.includes(i.type);
  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      {img ? (
        <Pressable onPress={() => i.close_image && setClose(!close)} accessibilityLabel="Photo of the incident">
          <Image source={{ uri: authUrl(`/images/${img}`) }} style={styles.photo} />
          {i.close_image ? (
            <View style={styles.photoTag}>
              <MaterialCommunityIcons name="swap-horizontal" size={14} color="#fff" />
              <Text style={styles.photoTagText}>{close ? 'Close-up' : 'When spotted'}</Text>
            </View>
          ) : null}
        </Pressable>
      ) : null}
      <View style={{ padding: 12, gap: 6 }}>
        <View style={styles.row}>
          <View style={[styles.flagIcon, { backgroundColor: visual ? p.dangerSoft : p.amberSoft }]}>
            <MaterialCommunityIcons name={FLAG_ICON[i.type] ?? 'alert'} size={18} color={visual ? p.danger : p.amber} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontFamily: fonts.heading, color: p.ink, fontSize: 15 }}>{i.title ?? 'Talking'}</Text>
            <Body small soft>{hhmm(i.ts)}{i.waypoint ? `, patrol spot ${i.waypoint}` : ''}{i.db ? `, ${Math.round(i.db)} dB` : ''}</Body>
          </View>
          {i.warned ? <Pill small level="warn" icon="account-voice" label="Warned" /> : null}
        </View>
        <Body small>{i.summary}</Body>
      </View>
    </Card>
  );
}

export default function Monitor() {
  const p = usePalette();
  const role = useAppSelector((s) => s.session.role);
  const zones = useAppSelector((s) => s.robot.zones).filter((z) => z.toLowerCase() !== 'home');
  const patrols = useAppSelector((s) => (s.robot.info as any)?.patrols ?? {}) as Record<string, number[][]>;
  const canRun = role === 'operator' || role === 'admin';
  const q = usePolling(() => api.monitor(), 3000, []);
  const caps = usePolling(() => api.monitorCaps(), 60000, []);
  const sessions = usePolling(() => api.monitorSessions(), 20000, []);
  const st = q.data;
  const [zone, setZone] = useState<string | null>(null);
  const [minutes, setMinutes] = useState(60);
  const [sens, setSens] = useState<'low' | 'normal' | 'high'>('normal');
  const [mode, setMode] = useState<'patrol' | 'stay'>('patrol');
  const [detect, setDetect] = useState<Record<DetectKey, boolean>>({ objects: true, head: true, looking_down: true, talking: true, whisper: true, noise: true });
  const [filter, setFilter] = useState<'all' | 'cheating' | 'sound'>('all');
  const [busy, setBusy] = useState(false);
  const [snack, setSnack] = useState('');
  const [open, setOpen] = useState<ExamSession | null>(null);
  const [viewing, setViewing] = useState<ExamSession | null>(null);
  const room = zone ?? zones.find((z) => /exam/i.test(z)) ?? zones[0] ?? null;

  const shown = viewing && !st?.active ? viewing : st;
  const incidents = useMemo(() => {
    const all = [...(shown?.incidents ?? [])].reverse();
    if (filter === 'cheating') return all.filter((i) => VISUAL.includes(i.type));
    if (filter === 'sound') return all.filter((i) => !VISUAL.includes(i.type ?? 'talking'));
    return all;
  }, [shown, filter]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    (st?.incidents ?? []).forEach((i) => { c[i.type] = (c[i.type] ?? 0) + 1; });
    return c;
  }, [st]);

  const start = async () => {
    setBusy(true);
    try {
      const r = await api.monitorStart(room, minutes, sens, mode, detect);
      setSnack(r.text ?? 'Monitoring started');
      setViewing(null);
      q.refresh();
    } catch (e: any) {
      setSnack(e.message);
    } finally {
      setBusy(false);
    }
  };
  const stop = async () => {
    setBusy(true);
    try {
      setSnack((await api.monitorStop()).text);
      q.refresh();
      sessions.refresh();
    } catch (e: any) {
      setSnack(e.message);
    } finally {
      setBusy(false);
    }
  };
  const exportPdf = async (id: string) => {
    try {
      const msg = await exportHtmlAsPdf(await api.monitorHtml(id), 'Share exam report');
      if (msg) setSnack(msg);
    } catch (e: any) {
      setSnack(e.message);
    }
  };
  const showSession = async (s: ExamSession) => {
    try {
      setViewing(await api.monitorSession(s.id));
      setOpen(null);
    } catch (e: any) {
      setSnack(e.message);
    }
  };

  // sound meter: 30..75 dB
  const pct = (v?: number | null) => Math.max(0, Math.min(1, ((v ?? 30) - 30) / 45));
  const loud = (st?.level_db ?? 0) >= (st?.baseline_db ?? 99) + 6;
  const routeLen = st?.route?.length ?? 0;
  const where = st?.phase === 'patrolling' && st.waypoint ? `Walking to spot ${st.waypoint} of ${routeLen}`
    : st?.phase === 'watching' && st.waypoint && routeLen > 1 ? `Watching from spot ${st.waypoint} of ${routeLen}`
      : PHASE[st?.phase ?? ''] ?? st?.phase;
  const hasRoute = room ? (patrols[room]?.length ?? 0) > 1 : false;
  const flagsTotal = st?.incidents?.length ?? 0;
  const past = (sessions.data ?? []).filter((s) => !(st?.active && s.id === st.id));

  return (
    <>
      <Screen onRefresh={() => { q.refresh(); sessions.refresh(); }}>
        {st?.active ? (
          <Card tone="console" style={{ marginTop: 8, gap: 14 }}>
            <View style={styles.row}>
              <View style={[styles.live, { backgroundColor: '#3DD598' }]} />
              <Text style={[styles.consoleTitle, { flex: 1 }]}>Monitoring {st.zone ? ZONE_LABEL(st.zone) : 'this room'}</Text>
              <ViewDial dir={st.phase === 'watching' ? st.view_dir : null} />
            </View>
            <Text style={styles.consoleBody}>
              {where}{st.minutes_left != null ? `. ${Math.ceil(st.minutes_left)} min left` : ''}
            </Text>
            <View style={styles.stats}>
              {[
                { v: flagsTotal, l: flagsTotal === 1 ? 'incident' : 'incidents' },
                { v: st.views ?? 0, l: 'views checked' },
                { v: st.students_seen ?? 0, l: 'students in view' },
              ].map((x) => (
                <View key={x.l} style={styles.stat}>
                  <Text style={styles.statV}>{x.v}</Text>
                  <Text style={styles.consoleSmall}>{x.l}</Text>
                </View>
              ))}
            </View>
            {Object.keys(counts).length ? (
              <View style={styles.chips}>
                {Object.entries(counts).map(([k, n]) => (
                  <View key={k} style={styles.countChip}>
                    <MaterialCommunityIcons name={FLAG_ICON[k as FlagType] ?? 'alert'} size={14} color="#FFB224" />
                    <Text style={styles.countText}>{n}</Text>
                  </View>
                ))}
              </View>
            ) : null}
            <View>
              <View style={[styles.meter, { backgroundColor: '#24325C' }]}>
                <View style={[styles.meterFill, { width: `${pct(st.level_db) * 100}%`, backgroundColor: loud ? '#FFB224' : '#1FC8E3' }]} />
                {st.baseline_db != null ? <View style={[styles.mark, { left: `${pct(st.baseline_db + 6) * 100}%` }]} /> : null}
              </View>
              <View style={[styles.row, { justifyContent: 'space-between', marginTop: 6 }]}>
                <Text style={styles.consoleSmall}>Sound {st.level_db != null ? `${Math.round(st.level_db)} dB` : '…'}</Text>
                <Text style={styles.consoleSmall}>Room quiet level {st.baseline_db != null ? `${Math.round(st.baseline_db)} dB` : '…'}</Text>
              </View>
            </View>
            <Button mode="contained" buttonColor="#D63B3B" icon="stop-circle-outline" onPress={stop} loading={busy} disabled={!canRun || busy}>
              Stop monitoring
            </Button>
          </Card>
        ) : (
          <>
            <Body soft style={{ marginTop: 8 }}>
              The robot walks around the exam room, turns its camera all the way round and listens. When it sees a phone,
              notes or an earpiece, a head turned to another paper, or hears talking, it goes to the student, asks them to
              stop and sends you a photo. It never tries to recognise who anyone is.
            </Body>
            {caps.data ? (
              <Card tone="sunken" style={[styles.row, { marginTop: 14, alignItems: 'flex-start' }]}>
                <MaterialCommunityIcons name={caps.data.mediapipe || caps.data.vision_ai ? 'cctv' : 'information-outline'} size={18} color={p.primary} />
                <Body small style={{ flex: 1 }}>{caps.data.text}</Body>
              </Card>
            ) : null}
            <Section title="Room">
              <View style={styles.chips}>
                {zones.map((z) => <Chip key={z} label={ZONE_LABEL(z)} active={room === z} onPress={() => setZone(z)} />)}
              </View>
            </Section>
            <Section title="How it moves" note={mode === 'patrol'
              ? (hasRoute ? `Walks the ${patrols[room!].length} spots of this room's route` : 'This room has no route yet: it stays in the middle and turns')
              : 'Stays in the middle of the room and turns round'}>
              <Segmented value={mode} onChange={setMode}
                options={[{ value: 'patrol', label: 'Walk around' }, { value: 'stay', label: 'Stay in place' }]} />
            </Section>
            <Section title="Watch for">
              <Card style={{ paddingVertical: 4 }}>
                {CHECKS.map((c, n) => (
                  <View key={c.key}>
                    {n ? <Divider inset={48} /> : null}
                    <ListRow icon={c.icon} title={c.label} detail={c.note}
                      onPress={() => setDetect({ ...detect, [c.key]: !detect[c.key] })}
                      right={<MaterialCommunityIcons name={detect[c.key] ? 'checkbox-marked-circle' : 'checkbox-blank-circle-outline'}
                        size={24} color={detect[c.key] ? p.primary : p.inkSoft} />} />
                  </View>
                ))}
              </Card>
            </Section>
            <Section title="How long">
              <View style={styles.chips}>
                {[30, 60, 90, 120, 180].map((m) => (
                  <Chip key={m} label={m < 60 ? `${m} min` : `${m / 60} h`.replace('1.5 h', '1½ h')} active={minutes === m} onPress={() => setMinutes(m)} />
                ))}
              </View>
            </Section>
            <Section title="How strict" note={sens === 'high' ? 'Acts on any whisper' : sens === 'low' ? 'Only acts on loud talking' : 'Acts on normal talking and repeated whispers'}>
              <Segmented value={sens} onChange={setSens}
                options={[{ value: 'low', label: 'Relaxed' }, { value: 'normal', label: 'Normal' }, { value: 'high', label: 'Strict' }]} />
            </Section>
            <Button mode="contained" icon="shield-account-outline" style={{ marginTop: 22 }} contentStyle={{ paddingVertical: 6 }}
              onPress={start} loading={busy} disabled={!canRun || busy || !room || !Object.values(detect).some(Boolean)}>
              Start monitoring {room ? ZONE_LABEL(room) : ''}
            </Button>
            {!canRun ? <Body small soft style={{ marginTop: 8 }}>Viewer accounts can watch sessions but not start them.</Body> : null}
          </>
        )}

        <Section title={st?.active ? 'This session' : viewing ? `Session of ${new Date(viewing.started * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : 'Last session'}
          note={!st?.active && shown?.stop_reason ? `Ended: ${shown.stop_reason}` : undefined}
          action={!st?.active && shown?.id ? (
            <Button compact icon="file-pdf-box" onPress={() => exportPdf(shown.id!)}>PDF</Button>) : undefined}>
          {(shown?.incidents?.length ?? 0) > 0 ? (
            <View style={[styles.chips, { marginBottom: 12 }]}>
              <Chip label="All" active={filter === 'all'} onPress={() => setFilter('all')} />
              <Chip label="Cheating" icon="eye-outline" active={filter === 'cheating'} onPress={() => setFilter('cheating')} />
              <Chip label="Sound" icon="ear-hearing" active={filter === 'sound'} onPress={() => setFilter('sound')} />
            </View>
          ) : null}
          {incidents.length === 0 ? (
            <EmptyState icon="shield-check-outline" title="Nothing flagged"
              body={st?.started ? 'Every incident appears here with a photo the moment it happens.' : 'Start a session to see incidents here.'} />
          ) : (
            <View style={{ gap: 10 }}>
              {incidents.map((i) => <IncidentCard key={`${i.ts}-${i.type}`} i={i} />)}
            </View>
          )}
        </Section>

        {past.length ? (
          <Section title="Past sessions">
            <Card style={{ paddingVertical: 4 }}>
              {past.slice(0, 10).map((s, n) => (
                <View key={s.id}>
                  {n ? <Divider inset={48} /> : null}
                  <ListRow icon="clipboard-text-clock-outline"
                    title={`${s.zone ? ZONE_LABEL(s.zone) : 'Room'}, ${new Date(s.started * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`}
                    detail={`${s.incident_count ? `${s.incident_count} incident${s.incident_count > 1 ? 's' : ''}` : 'No incidents'}, ${Math.round(((s.ended ?? s.started) - s.started) / 60)} min, ${s.mode === 'stay' ? 'stayed in place' : 'patrolled'}`}
                    right={s.incident_count ? <Pill small level="warn" label={String(s.incident_count)} /> : <Pill small level="ok" label="OK" />}
                    onPress={() => setOpen(s)} />
                </View>
              ))}
            </Card>
          </Section>
        ) : null}
      </Screen>

      <Sheet visible={!!open} onDismiss={() => setOpen(null)} title={open?.zone ? ZONE_LABEL(open.zone) : 'Exam session'}>
        {open ? (
          <View style={{ gap: 10 }}>
            <Body soft>
              {new Date(open.started * 1000).toLocaleString()}, {Math.round(((open.ended ?? open.started) - open.started) / 60)} min.{' '}
              {open.incident_count ? `${open.incident_count} incident${open.incident_count > 1 ? 's' : ''}.` : 'No incidents.'}
            </Body>
            <Button mode="contained" icon="format-list-bulleted" onPress={() => showSession(open)}>Show incidents</Button>
            <Button mode="outlined" icon="file-pdf-box" onPress={() => { const id = open.id; setOpen(null); exportPdf(id); }}>Export PDF report</Button>
          </View>
        ) : null}
      </Sheet>
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={5000}>{snack}</Snackbar>
    </>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  live: { width: 10, height: 10, borderRadius: 5 },
  consoleTitle: { fontFamily: fonts.display, fontSize: 21, color: '#EEF2FF', letterSpacing: -0.4 },
  consoleBody: { fontFamily: fonts.body, fontSize: 14.5, color: '#B8C3E6' },
  consoleSmall: { fontFamily: fonts.body, fontSize: 12.5, color: '#95A2C6' },
  stats: { flexDirection: 'row', gap: 10 },
  stat: { flex: 1, backgroundColor: '#1A2550', borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12 },
  statV: { fontFamily: fonts.display, fontSize: 22, color: '#EEF2FF' },
  countChip: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#2A2410', borderRadius: 99, paddingHorizontal: 10, paddingVertical: 4 },
  countText: { fontFamily: fonts.bodyStrong, fontSize: 13, color: '#FFD27A' },
  meter: { height: 12, borderRadius: 6, overflow: 'hidden' },
  meterFill: { height: '100%', borderRadius: 6 },
  mark: { position: 'absolute', top: -2, bottom: -2, width: 2, backgroundColor: '#EEF2FF' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  photo: { width: '100%', aspectRatio: 4 / 3 },
  photoTag: { position: 'absolute', right: 8, top: 8, flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#0D1530CC', borderRadius: 99, paddingHorizontal: 9, paddingVertical: 4 },
  photoTagText: { color: '#fff', fontFamily: fonts.bodyStrong, fontSize: 12 },
  flagIcon: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
});
