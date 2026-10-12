import { router } from 'expo-router';
import React, { useState } from 'react';
import { Platform, StyleSheet, Switch, View } from 'react-native';
import { Button, Snackbar, TextInput } from 'react-native-paper';

import { Body, Card, Divider, ListRow, Pill, Screen, Section, Segmented, Sheet } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { requestAlertPermission } from '@/services/alerts';
import { api } from '@/services/api';
import { findServer } from '@/services/discover';
import { tts } from '@/services/tts';
import { sessionActions, ThemeMode, useAppDispatch, useAppSelector } from '@/store';

export default function Settings() {
  const p = usePalette();
  const dispatch = useAppDispatch();
  const s = useAppSelector((st) => st.session);
  const t = useAppSelector((st) => st.robot.telemetry);
  const info = useAppSelector((st) => st.robot.info);
  const wsConnected = useAppSelector((st) => st.robot.wsConnected);
  const health = usePolling(() => api.health(), 20000, [s.serverUrl]);
  const [server, setServer] = useState(s.serverUrl);
  const [rid, setRid] = useState(s.robotId);
  const [snack, setSnack] = useState('');
  const [finding, setFinding] = useState(false);
  const [pw, setPw] = useState<{ cur: string; next: string } | null>(null);
  const [pwErr, setPwErr] = useState('');
  const isAdmin = s.role === 'admin';
  const canOperate = s.role === 'operator' || s.role === 'admin';
  const h = health.data;

  const run = (fn: () => Promise<string>) => async () => {
    try {
      setSnack(await fn());
    } catch (e: any) {
      setSnack(e.message);
    }
  };
  const changed = server.trim() !== s.serverUrl || rid.trim() !== s.robotId;
  const toggle = (value: boolean, onChange: (v: boolean) => void, disabled?: boolean) => (
    <Switch value={value} disabled={disabled} onValueChange={onChange} trackColor={{ true: p.primary, false: p.line }} />
  );

  return (
    <>
      <Screen>
        <Section title="Voice and sound" style={{ marginTop: 8 }}>
          <Card style={{ paddingVertical: 2 }}>
            <ListRow icon="account-voice" title="Read replies aloud" detail="Spoken commands always get a spoken answer"
              right={toggle(s.autoSpeak, (v) => dispatch(sessionActions.setPrefs({ autoSpeak: v })))} />
            <Divider inset={48} />
            <View style={{ paddingVertical: 12, gap: 8 }}>
              <Body small soft>Speaking speed</Body>
              <Segmented value={String(s.speechRate)} onChange={(v) => dispatch(sessionActions.setPrefs({ speechRate: Number(v) }))}
                options={[{ value: '0.85', label: 'Slower' }, { value: '1', label: 'Normal' }, { value: '1.15', label: 'Faster' }]} />
              <Button icon="play-circle-outline" compact style={{ alignSelf: 'flex-start' }}
                onPress={() => tts.speak('The air-conditioner in Lecture Hall B is running and the room is over-cooled at 18.5 degrees.')}>
                Test voice
              </Button>
            </View>
            <Divider inset={48} />
            <ListRow icon="microphone-outline" title="Voice recognition"
              detail={!h ? 'Checking…' : h.stt === 'none'
                ? (Platform.OS === 'web' ? 'Using this browser. For phones, run install_voice.bat on the server PC.' : 'Not set up on the server. Run install_voice.bat on the PC.')
                : `On the server: ${h.stt}`}
              right={h ? <Pill small level={h.stt === 'none' ? 'warn' : 'ok'} label={h.stt === 'none' ? 'Off' : 'Ready'} /> : undefined} />
          </Card>
        </Section>

        <Section title="Appearance">
          <Segmented<ThemeMode> value={s.themeMode} onChange={(v) => dispatch(sessionActions.setPrefs({ themeMode: v }))}
            options={[{ value: 'system', label: 'Automatic', icon: 'theme-light-dark' }, { value: 'light', label: 'Light', icon: 'white-balance-sunny' }, { value: 'dark', label: 'Dark', icon: 'weather-night' }]} />
        </Section>

        <Section title="Notifications">
          <Card style={{ paddingVertical: 2 }}>
            <ListRow icon="bell-ring-outline" title="Alerts on this device"
              detail="Poor air, obstacle stops, safe hold, low battery and finished inspections"
              right={toggle(s.notifications, async (v) => {
                if (v && Platform.OS !== 'web') {
                  const ok = await requestAlertPermission();
                  if (!ok) setSnack('Allow notifications for this app in your phone settings');
                }
                dispatch(sessionActions.setNotifications(v));
              })} />
          </Card>
        </Section>

        <Section title="Connection">
          <Card style={{ gap: 10 }}>
            <TextInput mode="outlined" dense label="Server address" value={server} onChangeText={setServer}
              autoCapitalize="none" autoCorrect={false} keyboardType="url" />
            <TextInput mode="outlined" dense label="Robot ID" value={rid} onChangeText={setRid} autoCapitalize="none" />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Button mode="contained" disabled={!changed} style={{ flex: 1 }}
                onPress={() => { dispatch(sessionActions.setServer({ serverUrl: server.trim(), robotId: rid.trim() })); setSnack('Saved. Reconnecting…'); }}>
                Save
              </Button>
              {Platform.OS !== 'web' ? (
                <Button mode="outlined" icon="qrcode-scan" onPress={() => router.push('/scan')} style={{ flex: 1 }}>Scan QR</Button>
              ) : null}
            </View>
            {Platform.OS !== 'web' ? (
              <Button mode="contained-tonal" icon="radar" loading={finding} disabled={finding}
                onPress={async () => {
                  setFinding(true);
                  try {
                    const f = await findServer({ known: [server, s.serverUrl].filter((u) => !u.startsWith('demo:')) });
                    if (!f) { setSnack('No Raqib server found on this Wi-Fi. Is start_backend.bat running on the PC?'); return; }
                    setServer(f.url);
                    dispatch(sessionActions.setServer({ serverUrl: f.url }));
                    setSnack(`Found ${f.site ?? 'the server'} at ${f.url}${f.online ? ', robot online' : ''}`);
                  } finally { setFinding(false); }
                }}>
                Find the server automatically
              </Button>
            ) : null}
            <View style={styles.status}>
              <Pill small level={wsConnected ? 'ok' : 'alert'} label={wsConnected ? 'Live link up' : 'No live link'} />
              <Pill small level={h?.mqtt_connected ? 'ok' : 'warn'} label={h?.mqtt_connected ? 'Robot link up' : 'Robot link unknown'} />
              <Pill small level={t ? 'ok' : 'idle'} label={t ? (t.simulation ? (info?.simulator === 'webots' ? 'Webots robot' : 'Simulated robot') : 'Real robot') : 'Robot offline'} />
            </View>
          </Card>
        </Section>

        {canOperate ? (
          <Section title="Robot">
            <Card style={{ paddingVertical: 2 }}>
              <ListRow icon="eye-off-outline" title="Privacy mode" detail="Camera off: no video, no photos (admin)"
                right={toggle(!!t?.privacy_mode, (v) => run(async () => {
                  await api.command(s.robotId, 'set_privacy', { enabled: v });
                  return v ? 'Privacy mode on' : 'Privacy mode off';
                })(), !isAdmin)} />
              <Divider inset={48} />
              <ListRow icon="restart" title="Release emergency stop" detail="Lets the robot move again after STOP"
                onPress={run(async () => { await api.reset(s.robotId); return 'Emergency stop released'; })} />
              {isAdmin ? (
                <>
                  <Divider inset={48} />
                  <ListRow icon="home-map-marker" title="Set this spot as the dock" detail="Re-zeros the robot's position"
                    onPress={run(async () => {
                      const r = await api.command(s.robotId, 'set_home');
                      return r.status === 'ok' ? 'Position reset. This spot is now the dock' : r.error;
                    })} />
                  <Divider inset={48} />
                  <ListRow icon="database-import-outline" title="Load demo history" detail="Adds 60 sample inspections for search demos"
                    onPress={run(async () => { const r = await api.seed(); return `Added ${r.seeded} sample inspections`; })} />
                </>
              ) : null}
            </Card>
          </Section>
        ) : null}

        <Section title="Account">
          <Card style={{ paddingVertical: 2 }}>
            <ListRow icon="form-textbox-password" title="Change password" onPress={() => { setPwErr(''); setPw({ cur: '', next: '' }); }} />
            <Divider inset={48} />
            <ListRow icon="logout" title="Sign out" danger onPress={() => dispatch(sessionActions.loggedOut())} />
          </Card>
        </Section>
      </Screen>

      <Sheet visible={!!pw} onDismiss={() => setPw(null)} title="Change password">
        {pw ? (
          <View style={{ gap: 12 }}>
            <TextInput mode="outlined" dense secureTextEntry label="Current password" value={pw.cur} onChangeText={(cur) => setPw({ ...pw, cur })} />
            <TextInput mode="outlined" dense secureTextEntry label="New password (6+ characters)" value={pw.next} onChangeText={(next) => setPw({ ...pw, next })} />
            {pwErr ? <Body small style={{ color: p.danger }}>{pwErr}</Body> : null}
            <Button mode="contained" disabled={!pw.cur || pw.next.length < 6} onPress={async () => {
              try { await api.changePassword(pw.cur, pw.next); setPw(null); setSnack('Password changed'); } catch (e: any) { setPwErr(e.message); }
            }}>Change password</Button>
          </View>
        ) : null}
      </Sheet>
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={3500}>{snack}</Snackbar>
    </>
  );
}

const styles = StyleSheet.create({
  status: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
});
