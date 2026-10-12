// Scheduled patrols: the robot runs a saved command at a set time on chosen days.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';
import { Button, Snackbar, TextInput } from 'react-native-paper';

import { Body, Card, Chip, EmptyState, IconBtn, Screen, Sheet } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { api } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts, timeAgo } from '@/theme';
import type { Schedule } from '@/types';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const PRESETS = [
  { name: 'Morning patrol', command: 'Patrol all rooms and return home', time: '07:45', days: [0, 1, 2, 3, 4] },
  { name: 'End-of-day energy check', command: 'Check the aircon in all rooms, then return home', time: '18:30', days: [0, 1, 2, 3, 4] },
  { name: 'Lab safety round', command: 'Inspect the IoT Lab, then return home', time: '13:00', days: [0, 2, 4] },
];

function daysText(d: number[]) {
  const s = [...d].sort().join('');
  if (s === '0123456') return 'Every day';
  if (s === '01234') return 'Weekdays';
  if (s === '56') return 'Weekends';
  return d.map((i) => DAYS[i]).join(', ');
}

export default function Schedules() {
  const p = usePalette();
  const role = useAppSelector((s) => s.session.role);
  const canEdit = role === 'operator' || role === 'admin';
  const q = usePolling(() => api.schedules(), 15000, []);
  const [edit, setEdit] = useState<Partial<Schedule> | null>(null);
  const [snack, setSnack] = useState('');
  const items = q.data ?? [];

  const toggle = async (s: Schedule, on: boolean) => {
    try {
      await api.enableSchedule(s.id, on);
      q.refresh();
    } catch (e: any) {
      setSnack(e.message);
    }
  };

  return (
    <>
      <Screen onRefresh={q.refresh}>
        <Body soft style={{ marginTop: 8 }}>
          The robot runs these on its own at the set time, saves a report and notifies everyone signed in.
        </Body>
        {items.length === 0 && q.data ? (
          <EmptyState icon="calendar-clock" title="No patrols scheduled"
            body="Start from a template below or create your own. A morning patrol catches problems before people arrive." />
        ) : null}
        <View style={{ gap: 10, marginTop: 14 }}>
          {items.map((s) => (
            <Card key={s.id} onPress={canEdit ? () => setEdit(s) : undefined} style={{ gap: 6 }}>
              <View style={styles.head}>
                <Text style={[styles.time, { color: s.enabled ? p.ink : p.inkFaint }]}>{s.time}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontFamily: fonts.heading, fontSize: 16, color: p.ink }}>{s.name}</Text>
                  <Body small soft>{daysText(s.days)}</Body>
                </View>
                <Switch value={s.enabled} disabled={!canEdit} onValueChange={(v) => toggle(s, v)}
                  trackColor={{ true: p.primary, false: p.line }} />
              </View>
              <Body small style={{ color: p.inkSoft }}>“{s.command}”</Body>
              {s.last_run ? (
                <Pressable disabled={!s.last_report} onPress={() => router.push(`/report/${s.last_report}`)} style={styles.last}>
                  <MaterialCommunityIcons name={s.last_status === 'ok' ? 'check-circle-outline' : s.last_status === 'running' ? 'progress-clock' : 'alert-circle-outline'}
                    size={15} color={s.last_status === 'ok' ? p.ok : s.last_status === 'running' ? p.primary : p.danger} />
                  <Body small soft>Last run {timeAgo(s.last_run)}{s.last_report ? ', open report' : ''}</Body>
                </Pressable>
              ) : null}
            </Card>
          ))}
        </View>
        {canEdit ? (
          <>
            <Button mode="contained" icon="plus" style={{ marginTop: 18 }} contentStyle={{ paddingVertical: 6 }}
              onPress={() => setEdit({ name: '', command: '', time: '08:00', days: [0, 1, 2, 3, 4], enabled: true })}>
              New schedule
            </Button>
            <Text style={{ fontFamily: fonts.heading, fontSize: 15, color: p.ink, marginTop: 24, marginBottom: 8 }}>Templates</Text>
            <View style={{ gap: 8 }}>
              {PRESETS.map((t) => (
                <Card key={t.name} tone="sunken" onPress={() => setEdit({ ...t, enabled: true })} style={styles.preset}>
                  <MaterialCommunityIcons name="calendar-plus" size={20} color={p.primary} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontFamily: fonts.bodyStrong, color: p.ink }}>{t.name}</Text>
                    <Body small soft>{t.time}, {daysText(t.days).toLowerCase()}</Body>
                  </View>
                </Card>
              ))}
            </View>
          </>
        ) : null}
      </Screen>
      <Editor value={edit} onClose={() => setEdit(null)} onSaved={(m) => { setEdit(null); setSnack(m); q.refresh(); }} />
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={3000}>{snack}</Snackbar>
    </>
  );
}

function Editor({ value, onClose, onSaved }: { value: Partial<Schedule> | null; onClose: () => void; onSaved: (msg: string) => void }) {
  const p = usePalette();
  const [v, setV] = useState<Partial<Schedule>>({});
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  React.useEffect(() => {
    if (value) {
      setV(value);
      setErr('');
    }
  }, [value]);
  const days = v.days ?? [];
  const validTime = /^([01]\d|2[0-3]):[0-5]\d$/.test(v.time ?? '');
  const save = async () => {
    setBusy(true);
    try {
      await api.saveSchedule({ ...v, name: v.name!.trim(), command: v.command!.trim(), time: v.time!, days } as any);
      onSaved(value?.id ? 'Schedule updated' : 'Schedule created');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  const bump = (mins: number) => {
    const [h, m] = (v.time ?? '08:00').split(':').map(Number);
    const t = ((h * 60 + m + mins) % 1440 + 1440) % 1440;
    setV({ ...v, time: `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}` });
  };
  return (
    <Sheet visible={!!value} onDismiss={onClose} title={value?.id ? 'Edit schedule' : 'New schedule'}>
      <View style={{ gap: 12 }}>
        <TextInput mode="outlined" label="Name" value={v.name ?? ''} onChangeText={(name) => setV({ ...v, name })} dense />
        <TextInput mode="outlined" label="What should the robot do?" value={v.command ?? ''} multiline
          placeholder="Patrol all rooms and return home" onChangeText={(command) => setV({ ...v, command })} />
        <View style={styles.timeRow}>
          <IconBtn icon="minus" label="Earlier" onPress={() => bump(-15)} />
          <TextInput mode="outlined" value={v.time ?? ''} onChangeText={(time) => setV({ ...v, time })} dense
            style={{ width: 110, textAlign: 'center' }} error={!validTime} keyboardType="numbers-and-punctuation" />
          <IconBtn icon="plus" label="Later" onPress={() => bump(15)} />
          <Body small soft style={{ flex: 1 }}>24-hour time on the server PC</Body>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {DAYS.map((d, i) => (
            <Chip key={d} label={d} active={days.includes(i)}
              onPress={() => setV({ ...v, days: days.includes(i) ? days.filter((x) => x !== i) : [...days, i] })} />
          ))}
        </View>
        {err ? <Body small style={{ color: p.danger }}>{err}</Body> : null}
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {value?.id ? (
            <>
              <Button mode="outlined" textColor={p.danger} onPress={async () => { await api.deleteSchedule(value.id!); onSaved('Schedule deleted'); }}>Delete</Button>
              <Button mode="outlined" icon="play" onPress={async () => {
                try { await api.runSchedule(value.id!); onSaved('Patrol started'); } catch (e: any) { setErr(e.message); }
              }}>Run now</Button>
            </>
          ) : null}
          <Button mode="contained" style={{ flex: 1 }} loading={busy}
            disabled={busy || !v.name?.trim() || (v.command ?? '').trim().length < 3 || !validTime || !days.length} onPress={save}>
            Save
          </Button>
        </View>
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  time: { fontFamily: fonts.numeric, fontSize: 26, letterSpacing: -0.5, minWidth: 74 },
  last: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  preset: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  timeRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
