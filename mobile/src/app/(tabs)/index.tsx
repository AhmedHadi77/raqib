import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Button, Snackbar } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import EStopButton from '@/components/EStopButton';
import FloorMap from '@/components/FloorMap';
import { Body, Logo, Metric, Pill, Screen, Section, Sheet, Wordmark } from '@/components/ui';
import VoiceButton from '@/components/VoiceButton';
import { usePalette, usePolling } from '@/hooks';
import { api } from '@/services/api';
import { ask } from '@/services/assistant';
import { useAppSelector } from '@/store';
import { COMFORT_LABEL, fonts, Level, levelColors, levelOf, pretty, STATE_LABEL, timeAgo, ZONE_LABEL } from '@/theme';

const EVENT_LABEL: Record<string, string> = {
  obstacle_stop: 'Stopped for an obstacle',
  obstacle_cleared: 'Path clear again',
  avoiding_obstacle: 'Driving around an obstacle',
  safe_hold: 'Lost the server connection and held still',
  cloud_restored: 'Server connection restored',
  gas_alert: 'Air-quality alert',
  low_battery: 'Battery low',
  privacy_mode: 'Privacy mode changed',
  inspection_complete: 'Inspection finished',
  manual_takeover: 'Manual control took over',
  talking_detected: 'Asked people to stop talking',
  monitoring_started: 'Exam monitoring started',
  monitoring_finished: 'Exam monitoring finished',
};

export default function Home() {
  const p = usePalette();
  const { robotId, role } = useAppSelector((s) => s.session);
  const { telemetry: t, online, wsConnected, events, info } = useAppSelector((s) => s.robot);
  const busy = useAppSelector((s) => s.chat.busy);
  const progress = useAppSelector((s) => s.chat.progress);
  const site = usePolling(() => api.health(), 60000, []);
  const [zone, setZone] = useState<string | null>(null);
  const [snack, setSnack] = useState('');
  const canDrive = role === 'operator' || role === 'admin';

  const mapQ = usePolling(() => api.map(robotId), 8000, [robotId]);
  const monQ = usePolling(() => api.monitor(), 6000, []);
  const mon = monQ.data;
  const histQ = usePolling(() => api.history(robotId, 15), 15000, [robotId]);
  const hist = histQ.data ?? [];
  const e = t?.environment;
  const rooms = Object.keys(mapQ.data?.zones ?? {}).filter((z) => z.toLowerCase() !== 'home');
  const status = mapQ.data?.status ?? {};
  const where = t?.pose?.zone ? (t.pose.zone.toLowerCase() === 'home' ? 'at the dock' : `in ${ZONE_LABEL(t.pose.zone)}`) : 'in the corridor';

  const run = (msg: string, zoneHint?: string | null) => {
    if (!canDrive) return setSnack('Viewer accounts can watch but not command the robot.');
    router.push('/chat');
    ask(msg, { zoneHint });
  };
  const command = async (label: string, action: string, params: Record<string, unknown> = {}) => {
    setSnack(`${label}…`);
    try {
      const r = await api.command(robotId, action, params);
      setSnack(r.status === 'ok' ? `${label}: done` : `${label}: ${r.error ?? r.status}`);
      mapQ.refresh();
    } catch (err: any) {
      setSnack(err.message);
    }
  };

  const headline = !online
    ? wsConnected ? 'Robot offline' : 'No connection'
    : mon?.active ? `Monitoring ${mon.zone ? ZONE_LABEL(mon.zone) : 'the exam'}`
    : t?.state === 'IDLE' ? `Ready ${where}` : t?.state === 'AUTONOMOUS_PATROL' ? `Working ${where}` : STATE_LABEL[t?.state ?? ''] ?? '…';
  const stateLevel: Level = !online || t?.state === 'EMERGENCY_STOP' || t?.state === 'SAFE_HOLD' ? 'alert'
    : t?.state === 'IDLE' ? 'ok' : 'warn';
  const batt = t?.battery?.percent;
  const findings = Object.values(status).reduce((n, s: any) => n + (s.issues || 0), 0);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: p.paper }}>
      <Screen onRefresh={() => { mapQ.refresh(); histQ.refresh(); }}>
        {/* ---------- brand bar */}
        <View style={styles.bar}>
          <Logo size={34} />
          <View style={{ flex: 1 }}>
            <Wordmark size={21} />
            <Body small soft numberOfLines={1}>{site.data?.site ?? 'Facility'}</Body>
          </View>
          <EStopButton compact />
        </View>

        {/* ---------- robot status */}
        <View style={{ marginTop: 18 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <View style={[styles.stateDot, { backgroundColor: levelColors(p, stateLevel).fg }]} />
            <Body small soft>{robotId.replace(/(\d+)$/, ' $1').replace(/^\w/, (c) => c.toUpperCase())}{t?.simulation ? (info?.simulator === 'webots' ? ', in Webots' : ', simulated') : ''}</Body>
          </View>
          <Text style={[styles.headline, { color: p.ink }]}>{headline}</Text>
          {busy ? (
            <View style={styles.progress}>
              <ActivityIndicator size="small" color={p.primary} />
              <Body small style={{ flex: 1, color: p.primary, fontFamily: fonts.bodyMedium }} numberOfLines={1}>{progress || 'Planning…'}</Body>
            </View>
          ) : null}
          <View style={styles.chips}>
            <Pill small level={batt == null ? 'idle' : batt < 20 ? 'alert' : batt < 40 ? 'warn' : 'ok'}
              icon={batt != null && batt < 20 ? 'battery-alert-variant-outline' : 'battery-high'}
              label={batt != null ? `${Math.round(batt)}%` : 'Battery n/a'} />
            <Pill small level={wsConnected ? 'ok' : 'alert'} icon={wsConnected ? 'access-point' : 'access-point-off'} label={wsConnected ? 'Live' : 'Reconnecting'} />
            {t?.faults?.length ? <Pill small level="warn" icon="wrench-outline" label={`${t.faults.length} part${t.faults.length > 1 ? 's' : ''} need attention`} /> : null}
            {findings ? <Pill small level="warn" icon="alert-circle-outline" label={`${findings} open finding${findings > 1 ? 's' : ''}`} /> : null}
          </View>
        </View>

        {/* ---------- exam monitoring in progress */}
        {mon?.active ? (
          <Pressable onPress={() => router.push('/monitor')} accessibilityRole="button"
            style={({ pressed }) => [styles.monBar, { backgroundColor: p.amberSoft, borderColor: p.amber, opacity: pressed ? 0.85 : 1 }]}>
            <MaterialCommunityIcons name="shield-account-outline" size={22} color={p.amber} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontFamily: fonts.heading, fontSize: 15, color: p.ink }}>
                Monitoring {mon.zone ? ZONE_LABEL(mon.zone) : 'the exam'}
              </Text>
              <Body small soft>
                {(mon.incidents?.length ?? 0) ? `${mon.incidents!.length} talking incident${mon.incidents!.length > 1 ? 's' : ''}` : 'Quiet so far'}
                {mon.minutes_left != null ? `, ${Math.ceil(mon.minutes_left)} min left` : ''}
              </Body>
            </View>
            <MaterialCommunityIcons name="chevron-right" size={20} color={p.inkSoft} />
          </Pressable>
        ) : null}

        {/* ---------- the building */}
        <View style={[styles.console, { backgroundColor: p.console, borderColor: p.consoleLine }]}>
          <View style={styles.consoleHead}>
            <Text style={{ fontFamily: fonts.heading, fontSize: 15, color: p.consoleInk, flex: 1 }}>Floor plan</Text>
            <Legend />
          </View>
          <FloorMap data={mapQ.data as any} pose={t?.pose as any} trail={hist} onZonePress={setZone} selected={zone} live={online} />
          <View style={styles.consoleActions}>
            <ConsoleBtn icon="map-marker-path" label="Patrol all" onPress={() => run('Patrol all rooms and return home')} disabled={!canDrive || busy} />
            <ConsoleBtn icon="air-conditioner" label="Check AC" onPress={() => run('Check the aircon in all rooms, then return home')} disabled={!canDrive || busy} />
            <ConsoleBtn icon="home-import-outline" label="Dock" onPress={() => command('Returning to dock', 'go_to_zone', { zone: 'Home' })} disabled={!canDrive} />
            <ConsoleBtn icon="gamepad-round-outline" label="Drive" onPress={() => router.push('/drive')} />
          </View>
        </View>

        {/* ---------- rooms */}
        <Section title="Rooms" note={rooms.length ? 'Latest result for each room. Tap one for actions.' : undefined}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10, paddingRight: 16 }} style={{ marginHorizontal: -16, paddingLeft: 16 }}>
            {rooms.map((z) => {
              const st: any = status[z];
              const lvl: Level = st?.level ?? 'idle';
              const c = levelColors(p, lvl);
              return (
                <Pressable key={z} onPress={() => setZone(z)} accessibilityRole="button"
                  style={({ pressed }) => [styles.room, { backgroundColor: p.surface, borderColor: p.line, opacity: pressed ? 0.85 : 1 }]}>
                  <View style={[styles.roomBar, { backgroundColor: st ? c.fg : p.line }]} />
                  <Text style={{ fontFamily: fonts.heading, fontSize: 16, color: p.ink }} numberOfLines={1}>{ZONE_LABEL(z)}</Text>
                  <Body small style={{ color: st ? c.fg : p.inkSoft, fontFamily: fonts.bodyStrong }}>
                    {!st ? 'Not inspected yet' : st.issues ? `${st.issues} finding${st.issues > 1 ? 's' : ''}` : 'All clear'}
                  </Body>
                  <Body small soft numberOfLines={1}>
                    {st ? `${COMFORT_LABEL[st.comfort] ?? pretty(st.comfort)}, ${timeAgo(st.ts)}` : 'Tap to inspect'}
                  </Body>
                </Pressable>
              );
            })}
            {!rooms.length ? <Body soft>Rooms appear when the robot connects.</Body> : null}
          </ScrollView>
        </Section>

        {/* ---------- live conditions */}
        <Section title="Where the robot is now" note={e?.warmed_up === false ? 'Sensors are settling after the move.' : undefined}>
          <View style={styles.grid}>
            <Metric icon="thermometer" label="Temperature" value={e?.temperature_c?.toFixed(1)} unit="°C" level={levelOf(e?.comfort_verdict)}
              note={COMFORT_LABEL[e?.comfort_verdict ?? ''] ?? pretty(e?.comfort_verdict)} trend={hist.map((h) => h.temperature_c)} />
            <Metric icon="water-percent" label="Humidity" value={e?.humidity_pct?.toFixed(0)} unit="%"
              note={e ? (e.humidity_pct > 60 ? 'Too humid' : e.humidity_pct < 40 ? 'Too dry' : 'In range') : undefined}
              level={e ? (e.humidity_pct > 60 || e.humidity_pct < 40 ? 'warn' : 'ok') : 'idle'} trend={hist.map((h) => h.humidity_pct)} />
            <Metric icon="weather-windy" label="Air quality" value={e?.aqi != null ? Math.round(e.aqi) : null} unit="AQI" level={levelOf(e?.gas_verdict)}
              note={e?.aqi_label} trend={hist.map((h) => h.aqi)} />
            <Metric icon="waveform" label="Sound" value={t?.audio?.db?.toFixed(0)} unit="dB" note={t?.audio?.title ?? 'Not sampled yet'}
              trend={hist.map((h) => h.db)} />
          </View>
        </Section>

        {/* ---------- activity */}
        <Section title="Activity" action={<Button compact onPress={() => router.push('/insights')}>Insights</Button>}>
          <View style={{ gap: 0 }}>
            {events.filter((ev) => ev.event !== 'state_change').length === 0 ? (
              <Body soft>Nothing yet. Missions, alerts and stops show up here as they happen.</Body>
            ) : null}
            {events.filter((ev) => ev.event !== 'state_change').slice(0, 6).map((ev, i, arr) => {
              const lvl: Level = ev.event === 'gas_alert' || ev.event === 'safe_hold' ? 'alert'
                : ev.event.includes('obstacle') || ev.event === 'low_battery' ? 'warn' : 'ok';
              const d: any = ev.data;
              return (
                <View key={`${ev.ts}-${i}`} style={styles.event}>
                  <View style={{ alignItems: 'center', width: 12 }}>
                    <View style={[styles.eventDot, { backgroundColor: levelColors(p, lvl).fg }]} />
                    {i < arr.length - 1 ? <View style={[styles.eventLine, { backgroundColor: p.line }]} /> : null}
                  </View>
                  <View style={{ flex: 1, paddingBottom: 14 }}>
                    <Body numberOfLines={1}>
                      {EVENT_LABEL[ev.event] ?? pretty(ev.event)}
                      {d?.zone ? ` in ${ZONE_LABEL(d.zone)}` : ev.event === 'inspection_complete' && d?.zones ? `: ${d.zones.map(ZONE_LABEL).join(', ')}` : ''}
                    </Body>
                    <Body small soft>{new Date(ev.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</Body>
                  </View>
                </View>
              );
            })}
          </View>
        </Section>
      </Screen>

      <View style={styles.fab} pointerEvents="box-none">
        <VoiceButton disabled={!canDrive} />
      </View>

      <RoomSheet zone={zone} status={zone ? (status as any)[zone] : null} canDrive={canDrive} onClose={() => setZone(null)}
        onAsk={(m) => { const z = zone; setZone(null); run(m, z); }}
        onDrive={() => { const z = zone!; setZone(null); command(`Driving to ${ZONE_LABEL(z)}`, 'go_to_zone', { zone: z }); }} />
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={3000} style={{ marginBottom: 80 }}>{snack}</Snackbar>
    </SafeAreaView>
  );
}

function Legend() {
  const p = usePalette();
  const items: [string, string][] = [['#3DD598', 'Clear'], ['#FFB224', 'Findings'], ['#FF6B6B', 'Urgent']];
  return (
    <View style={{ flexDirection: 'row', gap: 10 }}>
      {items.map(([c, l]) => (
        <View key={l} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
          <View style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: c }} />
          <Text style={{ fontFamily: fonts.body, fontSize: 11.5, color: p.consoleSoft }}>{l}</Text>
        </View>
      ))}
    </View>
  );
}

function ConsoleBtn({ icon, label, onPress, disabled }: { icon: any; label: string; onPress: () => void; disabled?: boolean }) {
  const p = usePalette();
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button"
      style={({ pressed }) => [styles.cBtn, { backgroundColor: pressed ? p.primary : p.console2, borderColor: p.consoleLine, opacity: disabled ? 0.4 : 1 }]}>
      <MaterialCommunityIcons name={icon} size={20} color={p.consoleInk} />
      <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 12, color: p.consoleInk }} numberOfLines={1}>{label}</Text>
    </Pressable>
  );
}

function RoomSheet({ zone, status, canDrive, onClose, onAsk, onDrive }: {
  zone: string | null; status: any; canDrive: boolean; onClose: () => void; onAsk: (m: string) => void; onDrive: () => void;
}) {
  const p = usePalette();
  const isHome = zone?.toLowerCase() === 'home';
  const name = isHome ? 'Dock' : ZONE_LABEL(zone);
  const lvl: Level = status?.level ?? 'idle';
  return (
    <Sheet visible={!!zone} onDismiss={onClose} title={name}>
      {status && !isHome ? (
        <View style={{ gap: 8, marginBottom: 14 }}>
          <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
            <Pill level={lvl} label={status.issues ? `${status.issues} finding${status.issues > 1 ? 's' : ''}` : 'All clear'} />
            {status.comfort ? <Pill level={levelOf(status.comfort)} label={COMFORT_LABEL[status.comfort] ?? pretty(status.comfort)} /> : null}
            {status.energy === 'WASTE' ? <Pill level="warn" icon="flash-outline" label="Energy waste" /> : null}
            {status.safety === 'HAZARD' ? <Pill level="alert" icon="alert-octagon-outline" label="Safety hazard" /> : null}
          </View>
          <Body small soft>Last inspected {timeAgo(status.ts)}.</Body>
        </View>
      ) : (
        <Body soft style={{ marginBottom: 14 }}>{isHome ? 'Where the robot parks and charges.' : 'Not inspected yet.'}</Body>
      )}
      <View style={{ gap: 8 }}>
        {!isHome ? (
          <>
            <Button mode="contained" icon="clipboard-check-outline" disabled={!canDrive} onPress={() => onAsk(`Inspect ${zone}`)}
              contentStyle={{ paddingVertical: 6 }}>Inspect this room</Button>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Button mode="outlined" icon="air-conditioner" style={{ flex: 1 }} disabled={!canDrive} onPress={() => onAsk(`Check the aircon in ${zone}`)}>Check AC</Button>
              <Button mode="outlined" icon="account-search-outline" style={{ flex: 1 }} disabled={!canDrive} onPress={() => onAsk(`Is anyone in ${zone}?`)}>Anyone in?</Button>
            </View>
          </>
        ) : null}
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button mode="outlined" icon="navigation-variant-outline" style={{ flex: 1 }} disabled={!canDrive} onPress={onDrive}>
            {isHome ? 'Return to dock' : 'Drive there'}
          </Button>
          {status?.report_id && !isHome ? (
            <Button mode="outlined" icon="file-document-outline" style={{ flex: 1 }}
              onPress={() => { onClose(); router.push(`/report/${status.report_id}`); }}>Last report</Button>
          ) : null}
        </View>
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 6 },
  stateDot: { width: 8, height: 8, borderRadius: 4 },
  headline: { fontFamily: fonts.display, fontSize: 30, lineHeight: 34, letterSpacing: -0.8, marginTop: 4 },
  progress: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 10 },
  console: { marginTop: 18, borderRadius: 20, borderWidth: 1, padding: 12, paddingTop: 12 },
  consoleHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 4, paddingHorizontal: 4 },
  consoleActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cBtn: { flex: 1, alignItems: 'center', gap: 4, paddingVertical: 10, borderRadius: 12, borderWidth: 1 },
  room: { width: 168, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, padding: 12, paddingTop: 14, gap: 3, overflow: 'hidden' },
  roomBar: { position: 'absolute', top: 0, left: 0, right: 0, height: 4 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  event: { flexDirection: 'row', gap: 12 },
  eventDot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
  eventLine: { width: 2, flex: 1, marginTop: 4 },
  fab: { position: 'absolute', bottom: 18, right: 18 },
  monBar: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 16, padding: 14, borderRadius: 16, borderWidth: 1 },
});
