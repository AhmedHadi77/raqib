// Robot health: every hardware part, the links between app/server/robot, and the AI services.
// Built for bring-up day: a part that is not wired yet shows what is wrong and how to fix it.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { Button } from 'react-native-paper';

import { Body, Card, Divider, Pill, Screen, Section } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { api } from '@/services/api';
import { useAppSelector } from '@/store';
import { APP_VERSION, fonts } from '@/theme';
import type { ComponentHealth } from '@/types';

// `what` describes the budget robot (the RM 500 build); `full` the bigger build with servos, BME680 and a UPS module.
const PARTS: { key: string; name: string; icon: any; what: string; full?: string }[] = [
  { key: 'power', name: 'Power', icon: 'power-plug-outline', what: 'Power bank → Pi; 2x18650 → motors', full: 'Battery, UPS module, Raspberry Pi' },
  { key: 'wiring', name: 'Wiring warning', icon: 'flash-alert-outline', what: 'From the Wiring Bench' },
  { key: 'motors', name: 'Drive motors', icon: 'engine-outline', what: 'L298N + 4 TT motors (4WD), speed on GPIO 13/19', full: 'PCA9685 + L298N' },
  { key: 'ultrasonic', name: 'Distance sensors', icon: 'signal-distance-variant', what: '3x HC-SR04, obstacle stop' },
  { key: 'encoders', name: 'Distance measuring', icon: 'rotate-3d-variant', what: 'Motor time + MPU6050 (no encoders)', full: 'Wheel encoders' },
  { key: 'imu', name: 'Motion sensor', icon: 'compass-outline', what: 'MPU6050, heading' },
  { key: 'environment', name: 'Air and climate', icon: 'thermometer-lines', what: 'AHT20 + BMP280 (no gas sensor)', full: 'BME680 + MQ-135' },
  { key: 'camera', name: 'Camera', icon: 'cctv', what: 'USB webcam, video and photos', full: 'Pi Camera, video and photos' },
  { key: 'pan_tilt', name: 'Looking around', icon: 'axis-arrow', what: 'Fixed camera: the robot turns to look', full: 'Pan / tilt servos' },
  { key: 'microphone', name: 'Microphone', icon: 'microphone-outline', what: "Webcam microphone: talking, alarms, machines", full: 'USB microphone' },
  { key: 'speaker', name: 'Speaker', icon: 'speaker', what: 'PAM8403 on the Pi audio jack', full: 'Spoken announcements' },
  { key: 'battery', name: 'Battery level', icon: 'battery-charging-outline', what: 'Not measured: see the power bank LEDs', full: 'UPS module gauge' },
  { key: 'i2c', name: 'I2C bus', icon: 'connection', what: 'MPU6050, AHT20 + BMP280', full: 'Shared sensor bus' },
];

function PartRow({ part, h, full }: { part: (typeof PARTS)[number]; h?: ComponentHealth; full?: boolean }) {
  const p = usePalette();
  const [open, setOpen] = useState(false);
  const ok = h?.ok;
  const color = h == null ? p.inkFaint : ok ? p.ok : p.danger;
  const what = (full && part.full) || part.what;
  return (
    <Pressable onPress={() => h && !ok && setOpen(!open)} disabled={!h || ok}>
      <View style={styles.part}>
        <View style={[styles.partIcon, { backgroundColor: h == null ? p.sunken : ok ? p.okSoft : p.dangerSoft }]}>
          <MaterialCommunityIcons name={part.icon} size={19} color={color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 15, color: p.ink }}>{part.name}</Text>
          <Body small soft numberOfLines={open ? undefined : 2}>{h ? (ok ? h.detail || what : h.detail) : what}</Body>
        </View>
        <MaterialCommunityIcons name={h == null ? 'help-circle-outline' : ok ? 'check-circle' : open ? 'chevron-up' : 'alert-circle'} size={20} color={color} />
      </View>
      {open && h?.hint ? (
        <View style={[styles.hint, { backgroundColor: p.sunken }]}>
          <MaterialCommunityIcons name="wrench-outline" size={16} color={p.inkSoft} style={{ marginTop: 2 }} />
          <Body small style={{ flex: 1 }}>{h.hint}</Body>
        </View>
      ) : null}
    </Pressable>
  );
}

function KV({ k, v, level }: { k: string; v: string; level?: 'ok' | 'warn' | 'alert' }) {
  const p = usePalette();
  return (
    <View style={styles.kv}>
      <Body soft style={{ flex: 1 }}>{k}</Body>
      {level ? <Pill small level={level} label={v} /> : <Text style={{ fontFamily: fonts.bodyMedium, color: p.ink, fontSize: 14.5 }}>{v}</Text>}
    </View>
  );
}

export default function Health() {
  const robotId = useAppSelector((s) => s.session.robotId);
  const role = useAppSelector((s) => s.session.role);
  const live = useAppSelector((s) => s.robot);
  const robot = usePolling(() => api.robot(robotId), 10000, [robotId]);
  const server = usePolling(() => api.health(), 10000, []);
  const [lat, setLat] = useState<string | null>(null);
  const [recheck, setRecheck] = useState<string | null>(null);
  const canOperate = role === 'operator' || role === 'admin';

  async function recheckParts() {
    setRecheck('Restarting the robot program to look for the parts again…');
    try {
      const ack = await api.command(robotId, 'recheck_hardware', {});
      if (ack?.result?.restarting === false) { setRecheck('Simulation: there are no real parts to look for.'); return; }
      setTimeout(() => { robot.refresh(); setRecheck('Done. The list below shows what the robot found.'); }, 9000);
    } catch (e: any) {
      setRecheck(e.message);
    }
  }
  const t = live.telemetry ?? robot.data?.telemetry ?? null;
  const info = robot.data?.info ?? live.info;
  const health = t?.health ?? info?.health ?? {};
  const faults = PARTS.filter((x) => health[x.key] && !health[x.key].ok);
  const h = server.data;
  const sim = t?.simulation ?? info?.simulation;
  const full = info?.hardware_profile === 'full';

  return (
    <Screen onRefresh={() => { robot.refresh(); server.refresh(); }}>
      <Card tone="console" style={{ marginTop: 8, gap: 6 }}>
        <Text style={{ fontFamily: fonts.display, fontSize: 22, color: '#EEF2FF' }}>
          {!live.online ? 'Robot offline' : faults.length ? `${faults.length} part${faults.length > 1 ? 's' : ''} need attention` : 'All systems working'}
        </Text>
        <Text style={{ fontFamily: fonts.body, fontSize: 14, color: '#95A2C6', lineHeight: 20 }}>
          {info?.simulator === 'webots' ? 'Running in the Webots 3D simulator: motors, wheel encoders, sonars, IMU, camera and speaker are simulated in 3D; climate, gas and microphone are modelled per room. ' : ''}{sim ? `Running in simulation${full ? '' : ' as the reliable RM 500 robot (4WD, webcam, AHT20, power bank, no servos, no encoders, no gas sensor)'}. When the real parts are wired, set simulation: false on the robot and this list shows each one.`
            : faults.length ? 'Tap a red item to see how to fix it. The robot keeps working with the parts it has, and refuses to drive forward without its distance sensors.'
              : 'Every motor and sensor answered at start-up.'}
        </Text>
      </Card>

      {!live.online ? (
        <Card style={{ marginTop: 12, gap: 8 }}>
          <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 15, color: '#B87300' }}>The robot is not connected yet</Text>
          {[
            'Switch the robot on and wait about one minute for it to start.',
            'Robot, phone and the PC must be on the same Wi-Fi.',
            'On the PC, start_backend.bat must be running. The robot finds it by itself.',
            'Still offline? On the PC run allow_robot_connections.bat once (Windows Firewall).',
          ].map((x, i) => (
            <View key={x} style={{ flexDirection: 'row', gap: 8 }}>
              <Text style={{ fontFamily: fonts.bodyStrong, width: 18 }}>{i + 1}.</Text>
              <Body small style={{ flex: 1 }}>{x}</Body>
            </View>
          ))}
        </Card>
      ) : !sim && canOperate ? (
        <Card style={{ marginTop: 12, gap: 6 }}>
          <Body small soft>Plugged in a part after the robot started? Let the robot look again.</Body>
          <Button mode="contained-tonal" icon="refresh" style={{ alignSelf: 'flex-start' }} onPress={recheckParts}
            disabled={!!recheck && recheck.startsWith('Restarting')}>Re-check parts</Button>
          {recheck ? <Body small>{recheck}</Body> : null}
        </Card>
      ) : null}

      {h?.warnings?.length ? (
        <Card style={{ marginTop: 12, gap: 8, borderColor: '#B87300' }}>
          {h.warnings.map((w) => (
            <View key={w} style={{ flexDirection: 'row', gap: 8 }}>
              <MaterialCommunityIcons name="alert-outline" size={18} color="#B87300" style={{ marginTop: 1 }} />
              <Body small style={{ flex: 1 }}>{w}</Body>
            </View>
          ))}
        </Card>
      ) : null}

      <Section title="Hardware">
        <Card style={{ paddingVertical: 2 }}>
          {PARTS.filter((x) => !['i2c', 'power', 'wiring'].includes(x.key) || health[x.key]).map((part, i) => (
            <View key={part.key}>
              {i ? <Divider inset={48} /> : null}
              <PartRow part={part} h={health[part.key]} full={full} />
            </View>
          ))}
        </Card>
      </Section>

      <Section title="Connections">
        <Card style={{ gap: 2 }}>
          <KV k="App to server" v={live.wsConnected ? 'Connected' : 'Reconnecting'} level={live.wsConnected ? 'ok' : 'alert'} />
          <KV k="Server to robot (MQTT)" v={h?.mqtt_connected ? 'Connected' : 'Down'} level={h?.mqtt_connected ? 'ok' : 'alert'} />
          <KV k="Robot" v={live.online ? 'Online' : 'Offline'} level={live.online ? 'ok' : 'alert'} />
          <KV k="Command round-trip" v={lat ?? 'not measured'} />
          <Button icon="speedometer" compact style={{ alignSelf: 'flex-start', marginTop: 4 }}
            onPress={async () => { setLat('measuring…'); try { const r = await api.ping(robotId); setLat(r.median_ms != null ? `${r.median_ms} ms` : 'no reply'); } catch (e: any) { setLat(e.message); } }}>
            Measure
          </Button>
        </Card>
      </Section>

      <Section title="Safety">
        <Card style={{ gap: 2 }}>
          <KV k="Obstacle stop distance" v={`${t?.safety?.stop_distance_cm ?? 15} cm`} />
          <KV k="Last emergency stop" v={t?.safety?.last_stop_latency_ms != null ? `${t.safety.last_stop_latency_ms} ms (target under 50)` : 'none yet'} />
          <KV k="Safety loop worst case" v={t?.safety?.max_loop_ms != null ? `${t.safety.max_loop_ms} ms` : '—'} />
          <KV k="Server heartbeat" v={t?.safety ? `${t.safety.cloud_silent_s} s ago` : '—'} level={t?.safety && t.safety.cloud_silent_s > 5 ? 'warn' : undefined} />
        </Card>
      </Section>

      <Section title="AI services" action={role === 'admin' ? <Button compact onPress={() => router.push('/ai' as any)}>Change</Button> : undefined}>
        <Card style={{ gap: 2 }}>
          <KV k="Command planner" v={h?.planner === 'rules' ? 'Built-in (offline)' : h?.planner ?? '—'} />
          <KV k="Vision" v={h?.vlm === 'mock' ? 'Simulator (no model)' : h?.vlm ?? '—'} />
          <KV k="Voice recognition" v={!h ? '—' : h.stt === 'none' ? 'Off (browser only)' : h.stt} level={h?.stt === 'none' ? 'warn' : undefined} />
          <KV k="Exam proctoring camera" v={!h?.proctor ? '—' : h.proctor.mode === 'off' ? 'Off' : h.proctor.mediapipe ? (h.proctor.vision_ai ? 'MediaPipe + vision AI' : 'MediaPipe on the server') : h.proctor.vision_ai ? 'Vision AI' : 'Sound only'}
            level={h?.proctor && !h.proctor.mediapipe && !h.proctor.vision_ai ? 'warn' : undefined} />
          <KV k="Sound classifier" v={info?.audio_model === 'edge_impulse' ? 'Edge Impulse model' : 'Built-in rules'} />
          <KV k="Inspection memory" v={h?.memory ? `${h.memory.records} records` : '—'} />
        </Card>
      </Section>

      <Section title="Versions">
        <Card style={{ gap: 2 }}>
          <KV k="App" v={APP_VERSION} />
          <KV k="Server" v={h?.version ?? '—'} />
          <KV k="Robot software" v={info?.software?.version ?? '—'} />
        </Card>
      </Section>
    </Screen>
  );
}

const styles = StyleSheet.create({
  part: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11 },
  partIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  hint: { flexDirection: 'row', gap: 8, padding: 10, borderRadius: 10, marginBottom: 10, marginLeft: 48 },
  kv: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 7 },
});
