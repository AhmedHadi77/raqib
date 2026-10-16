// Drive console: live camera, 8-way pad / joystick, look-around (pan-tilt or turning the robot), precise moves and voice driving.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useFocusEffect } from 'expo-router';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { Snackbar } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { CameraPad, DrivePad, Joystick } from '@/components/DriveControls';
import EStopButton from '@/components/EStopButton';
import { Segmented } from '@/components/ui';
import VideoView from '@/components/VideoView';
import VoiceButton from '@/components/VoiceButton';
import { usePalette } from '@/hooks';
import { api } from '@/services/api';
import { ask } from '@/services/assistant';
import { Dir, dirToWheels, drive } from '@/services/drive';
import { sessionActions, useAppDispatch, useAppSelector } from '@/store';
import { fonts, STATE_LABEL } from '@/theme';

type Mode = 'pad' | 'stick' | 'camera';

const KEYMAP: Record<string, Dir> = {
  ArrowUp: 'f', w: 'f', ArrowDown: 'b', s: 'b', ArrowLeft: 'l', a: 'l', ArrowRight: 'r', d: 'r', q: 'fl', e: 'fr', z: 'bl', c: 'br',
};

export default function Drive() {
  const p = usePalette();
  const dispatch = useAppDispatch();
  const { width } = useWindowDimensions();
  const wide = width >= 900;
  const { robotId, role, driveSpeed } = useAppSelector((s) => s.session);
  const { telemetry: t, online, info } = useAppSelector((s) => s.robot);
  const fixedCam = !!info?.fixed_camera;
  const [mode, setMode] = useState<Mode>('pad');
  const [snack, setSnack] = useState('');
  const [keyDir, setKeyDir] = useState<Dir | null>(null);
  const [cam, setCam] = useState({ pan: 0, tilt: 0 });
  const canDrive = (role === 'operator' || role === 'admin') && online;
  const latched = t?.state === 'EMERGENCY_STOP' || t?.state === 'SAFE_HOLD';

  useEffect(() => drive.subscribe((_v, err) => err && setSnack(err)), []);
  useEffect(() => {
    if (t?.pan_tilt) setCam({ pan: t.pan_tilt.pan, tilt: t.pan_tilt.tilt });
    // first telemetry after mount; on the budget robot also whenever driving resets the look angle
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!t, fixedCam ? t?.pan_tilt?.pan : 0]);
  // leaving the screen always stops the wheels
  useFocusEffect(useCallback(() => () => { if (drive.active) drive.stop(); }, []));

  // keyboard driving on computers (arrows / WASD, Q E Z C diagonals, space = stop)
  const held = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    const apply = () => {
      const k = [...held.current].reverse().find((x) => KEYMAP[x]);
      if (!k) {
        setKeyDir(null);
        if (drive.active) drive.stop();
        return;
      }
      const d = KEYMAP[k];
      setKeyDir(d);
      const [l, r] = dirToWheels(d, driveSpeed);
      drive.set(l, r);
    };
    const down = (ev: KeyboardEvent) => {
      if ((ev.target as HTMLElement)?.tagName === 'INPUT' || !canDrive) return;
      const k = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
      if (k === ' ') {
        ev.preventDefault();
        held.current.clear();
        drive.stop();
        setKeyDir(null);
        return;
      }
      if (!KEYMAP[k] || held.current.has(k)) return;
      ev.preventDefault();
      held.current.add(k);
      apply();
    };
    const up = (ev: KeyboardEvent) => {
      const k = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
      if (held.current.delete(k)) apply();
    };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
    };
  }, [canDrive, driveSpeed]);

  const precise = async (label: string, action: string, params: Record<string, unknown>) => {
    setSnack(`${label}…`);
    try {
      const r = await api.command(robotId, action, params);
      setSnack(r.status === 'ok' ? `${label}: done` : `${label}: ${r.error ?? r.status}`);
    } catch (e: any) {
      setSnack(e.message);
    }
  };
  const moveCam = (pan: number, tilt: number) => {
    setCam({ pan, tilt });
    api.command(robotId, 'pan_tilt', { pan, tilt }, false).catch((e) => setSnack(e.message));
  };

  const u = t?.ultrasonic_cm;
  const stopAt = t?.safety?.stop_distance_cm ?? 15;
  const near = (d?: number) => (d == null ? p.consoleSoft : d < stopAt ? '#FF6B6B' : d < 45 ? '#FFB224' : '#3DD598');
  const speedPct = t?.motors ? Math.round(((Math.abs(t.motors.left) + Math.abs(t.motors.right)) / 2) * 100) : 0;

  const video = (
    <View>
      <VideoView />
      {t?.safety?.blocked ? (
        <View style={styles.blocked}>
          <MaterialCommunityIcons name="alert-octagon" size={16} color="#fff" />
          <Text style={styles.blockedText}>Obstacle ahead, forward driving is paused</Text>
        </View>
      ) : null}
      <View style={styles.sonar} pointerEvents="none">
        {(['left', 'center', 'right'] as const).map((k) => {
          const d = u?.[k];
          return (
            <View key={k} style={{ flex: k === 'center' ? 1.4 : 1, alignItems: 'center', gap: 3 }}>
              <View style={[styles.sonarBar, { backgroundColor: near(d) }]} />
              <Text style={styles.sonarText}>{d == null ? '—' : d >= 400 ? 'clear' : `${Math.round(d)} cm`}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );

  const readouts = (
    <View style={[styles.readouts, { borderColor: p.consoleLine }]}>
      <Readout label="Heading" value={t?.pose ? `${Math.round(((t.pose.heading_deg % 360) + 360) % 360)}°` : '—'} />
      <Readout label="Power" value={`${speedPct}%`} />
      <Readout label="Position" value={t?.pose ? `${fmt1(t.pose.x)}, ${fmt1(t.pose.y)}` : '—'} />
      <Readout label="Front" value={u?.center == null ? '—' : u.center >= 400 ? 'clear' : `${Math.round(u.center)} cm`} />
    </View>
  );

  const controls = (
    <View style={{ gap: 14 }}>
      <Segmented dark value={mode} onChange={setMode} options={[
        { value: 'pad', label: 'Pad', icon: 'gamepad-variant-outline' },
        { value: 'stick', label: 'Joystick', icon: 'axis-arrow' },
        { value: 'camera', label: fixedCam ? 'Look' : 'Camera', icon: 'cctv' },
      ]} />
      <View style={styles.controlArea}>
        {mode === 'pad' ? <DrivePad speed={driveSpeed} disabled={!canDrive || latched} active={keyDir} /> : null}
        {mode === 'stick' ? <Joystick speed={driveSpeed} disabled={!canDrive || latched} /> : null}
        {mode === 'camera' ? (
          <View style={{ alignItems: 'center', gap: 14 }}>
            <CameraPad pan={cam.pan} tilt={cam.tilt} onMove={moveCam} disabled={!canDrive || (fixedCam && latched)} fixed={fixedCam} />
            <Pressable disabled={!canDrive} onPress={() => { ask('What do you see?'); setSnack('Analysing the view… the answer appears in Assistant'); }}
              style={({ pressed }) => [styles.analyse, { backgroundColor: pressed ? p.primary : p.console2, borderColor: p.consoleLine, opacity: canDrive ? 1 : 0.4 }]}>
              <MaterialCommunityIcons name="eye-outline" size={18} color={p.consoleInk} />
              <Text style={{ color: p.consoleInk, fontFamily: fonts.bodyStrong }}>What do you see?</Text>
            </Pressable>
          </View>
        ) : null}
      </View>
      {mode !== 'camera' ? (
        <>
          <View>
            <Text style={[styles.label, { color: p.consoleSoft }]}>Speed</Text>
            <Segmented dark value={String(driveSpeed)} onChange={(v) => dispatch(sessionActions.setPrefs({ driveSpeed: Number(v) }))} options={[
              { value: '0.35', label: 'Slow' }, { value: '0.6', label: 'Normal' }, { value: '0.9', label: 'Fast' },
            ]} />
          </View>
          <View>
            <Text style={[styles.label, { color: p.consoleSoft }]}>Exact moves</Text>
            <View style={styles.moves}>
              <MoveBtn icon="arrow-up" label="50 cm" onPress={() => precise('Forward 50 cm', 'move', { distance_m: 0.5 })} disabled={!canDrive} />
              <MoveBtn icon="arrow-down" label="50 cm" onPress={() => precise('Back 50 cm', 'move', { distance_m: -0.5 })} disabled={!canDrive} />
              <MoveBtn icon="rotate-left" label="90°" onPress={() => precise('Turn left', 'turn', { angle_deg: 90 })} disabled={!canDrive} />
              <MoveBtn icon="rotate-right" label="90°" onPress={() => precise('Turn right', 'turn', { angle_deg: -90 })} disabled={!canDrive} />
              <MoveBtn icon="backup-restore" label="U-turn" onPress={() => precise('U-turn', 'turn', { angle_deg: 180 })} disabled={!canDrive} />
            </View>
          </View>
        </>
      ) : null}
      {Platform.OS === 'web' ? (
        <Text style={{ color: p.consoleSoft, fontFamily: fonts.body, fontSize: 12.5, textAlign: 'center' }}>
          Keyboard: arrows or W A S D to drive, Q E Z C for curves, space to stop.
        </Text>
      ) : null}
      {!canDrive ? (
        <Text style={{ color: '#FFB224', fontFamily: fonts.bodyMedium, textAlign: 'center' }}>
          {!online ? 'The robot is offline.' : 'Viewer accounts can watch but not drive.'}
        </Text>
      ) : latched ? (
        <Text style={{ color: '#FF8A8A', fontFamily: fonts.bodyMedium, textAlign: 'center' }}>
          {t?.state === 'SAFE_HOLD' ? 'Safe hold: waiting for the server link to return.' : 'Emergency stop is on. Release it to drive.'}
        </Text>
      ) : null}
    </View>
  );

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: p.console }}>
      <View style={styles.top}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: fonts.display, fontSize: 24, color: p.consoleInk, letterSpacing: -0.5 }}>Drive</Text>
          <Text style={{ fontFamily: fonts.body, fontSize: 13, color: p.consoleSoft }}>
            {online ? `${STATE_LABEL[t?.state ?? ''] ?? '…'}, battery ${t?.battery?.percent != null ? Math.round(t.battery.percent) + '%' : 'on power bank'}` : 'Robot offline'}
          </Text>
        </View>
        <VoiceButton size={42} disabled={!canDrive} panelOffset={24} />
        <EStopButton compact />
      </View>
      <ScrollView contentContainerStyle={[styles.body, wide && { flexDirection: 'row', alignItems: 'flex-start' }]}>
        <View style={wide ? { flex: 1.3, gap: 12 } : { gap: 12 }}>
          {video}
          {readouts}
        </View>
        <View style={wide ? { flex: 1 } : { marginTop: 16 }}>{controls}</View>
      </ScrollView>
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={2500} style={{ marginBottom: 80 }}>{snack}</Snackbar>
    </SafeAreaView>
  );
}

const fmt1 = (v: number) => (Math.abs(v) < 0.05 ? '0.0' : v.toFixed(1));

function Readout({ label, value }: { label: string; value: string }) {
  const p = usePalette();
  return (
    <View style={{ flex: 1, alignItems: 'flex-start', gap: 2 }}>
      <Text style={{ fontFamily: fonts.body, fontSize: 11.5, color: p.consoleSoft }}>{label}</Text>
      <Text style={{ fontFamily: fonts.numeric, fontSize: 15, color: p.consoleInk }} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function MoveBtn({ icon, label, onPress, disabled }: { icon: any; label: string; onPress: () => void; disabled?: boolean }) {
  const p = usePalette();
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityRole="button" accessibilityLabel={`${icon} ${label}`}
      style={({ pressed }) => [styles.move, { backgroundColor: pressed ? p.primary : p.console2, borderColor: p.consoleLine, opacity: disabled ? 0.4 : 1 }]}>
      <MaterialCommunityIcons name={icon} size={18} color={p.consoleInk} />
      <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 12, color: p.consoleInk }}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 10, gap: 10 },
  body: { padding: 16, paddingTop: 4, paddingBottom: 120, gap: 16, width: '100%', maxWidth: 1180, alignSelf: 'center' },
  blocked: { position: 'absolute', top: 44, left: 10, right: 10, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#D63B3BE6', paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10 },
  blockedText: { color: '#fff', fontFamily: fonts.bodyStrong, fontSize: 13.5 },
  sonar: { position: 'absolute', left: 10, right: 10, bottom: 10, flexDirection: 'row', gap: 8 },
  sonarBar: { height: 5, borderRadius: 3, alignSelf: 'stretch' },
  sonarText: { color: '#fff', fontFamily: fonts.bodyStrong, fontSize: 11.5, textShadowColor: '#000', textShadowRadius: 3 },
  readouts: { flexDirection: 'row', borderWidth: 1, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12, gap: 8 },
  controlArea: { alignItems: 'center', minHeight: 226, justifyContent: 'center' },
  label: { fontFamily: fonts.bodyMedium, fontSize: 12.5, marginBottom: 6, marginLeft: 4 },
  moves: { flexDirection: 'row', gap: 8 },
  move: { flex: 1, alignItems: 'center', gap: 2, paddingVertical: 9, borderRadius: 12, borderWidth: 1 },
  analyse: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 18, paddingVertical: 12, borderRadius: 999, borderWidth: 1 },
  fab: { position: 'absolute', right: 18, bottom: 18 },
});
