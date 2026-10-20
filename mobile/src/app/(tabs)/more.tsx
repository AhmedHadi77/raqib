import { router } from 'expo-router';
import React from 'react';
import { Linking, Platform, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Body, Card, Divider, ListRow, Logo, Pill, Screen, Section, Wordmark } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { api } from '@/services/api';
import { sessionActions, useAppDispatch, useAppSelector } from '@/store';
import { APP_VERSION, fonts } from '@/theme';

const ROLE_TEXT = { admin: 'Administrator', operator: 'Operator', viewer: 'Viewer' } as const;

export default function More() {
  const p = usePalette();
  const dispatch = useAppDispatch();
  const { username, name, role } = useAppSelector((s) => s.session);
  const faults = useAppSelector((s) => s.robot.telemetry?.faults ?? []);
  const sim = useAppSelector((s) => s.robot.simulation);
  const sched = usePolling(() => api.schedules(), 60000, []);
  const health = usePolling(() => api.health(), 30000, []);
  const active = (sched.data ?? []).filter((s) => s.enabled);
  const { serverUrl, token } = useAppSelector((s) => s.session);
  const openBench = () => {
    const url = `${serverUrl}/bench#t=${encodeURIComponent(token ?? '')}`;
    if (Platform.OS === 'web') window.open(url, '_blank');
    else Linking.openURL(url);
  };
  const initials = (name || username || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: p.paper }}>
      <Screen>
        <Text style={{ fontFamily: fonts.display, fontSize: 24, color: p.ink, letterSpacing: -0.5, marginTop: 8 }}>More</Text>

        <Card style={[styles.profile, { marginTop: 14 }]} onPress={() => router.push('/settings')}>
          <View style={[styles.avatar, { backgroundColor: p.primarySoft }]}>
            <Text style={{ fontFamily: fonts.heading, fontSize: 18, color: p.primary }}>{initials}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontFamily: fonts.heading, fontSize: 17, color: p.ink }}>{name || username}</Text>
            <Body small soft>{role ? ROLE_TEXT[role] : ''}, signed in as {username}</Body>
          </View>
        </Card>

        <Section title="Operations">
          <Card style={{ paddingVertical: 2 }}>
            <ListRow icon="shield-account-outline" title="Exam monitor"
              detail="Patrols the exam: phones, notes, earpieces, wandering eyes, talking" onPress={() => router.push('/monitor')} />
            <Divider inset={48} />
            {!serverUrl.startsWith('demo:') ? (
              <>
                <ListRow icon="chip" title="Wiring Bench"
                  detail="Wire every part to the XIAO ESP32S3; the simulated robot works only when it is wired right"
                  onPress={openBench} />
                <Divider inset={48} />
              </>
            ) : null}
            <ListRow icon="chart-timeline-variant" title="Insights" detail="Trends and search across past inspections" onPress={() => router.push('/insights')} />
            <Divider inset={48} />
            <ListRow icon="calendar-clock" title="Scheduled patrols"
              detail={active.length ? `${active.length} active, next at ${active.map((s) => s.time).sort()[0]}` : 'Run inspections automatically every day'}
              onPress={() => router.push('/schedules')} />
            <Divider inset={48} />
            <ListRow icon="stethoscope" title="Robot health"
              detail={faults.length ? `${faults.length} part${faults.length > 1 ? 's' : ''} need attention` : sim ? 'Simulated robot, all parts OK' : 'Motors, sensors, camera and battery'}
              right={faults.length ? <Pill small level="alert" label={String(faults.length)} /> : undefined}
              onPress={() => router.push('/health')} />
          </Card>
        </Section>

        {role === 'admin' ? (
          <Section title="Administration">
            <Card style={{ paddingVertical: 2 }}>
              <ListRow icon="account-group-outline" title="Users" detail="Add people and choose what they can do" onPress={() => router.push('/users')} />
              <Divider inset={48} />
              <ListRow icon="creation" title="AI settings"
                detail={!health.data ? 'Connect Gemini, OpenAI or Ollama' : health.data.planner === 'rules' ? 'Not connected: the robot only knows the built-in commands' : `Connected: ${health.data.planner.replace('llm:', '')}`}
                right={health.data ? <Pill small level={health.data.planner === 'rules' ? 'warn' : 'ok'} label={health.data.planner === 'rules' ? 'Off' : 'On'} /> : undefined}
                onPress={() => router.push('/ai' as any)} />
            </Card>
          </Section>
        ) : null}

        <Section title="App">
          <Card style={{ paddingVertical: 2 }}>
            <ListRow icon="tune-variant" title="Settings" detail="Connection, voice, appearance, notifications" onPress={() => router.push('/settings')} />
            <Divider inset={48} />
            <ListRow icon="logout" title="Sign out" danger onPress={() => dispatch(sessionActions.loggedOut())} />
          </Card>
        </Section>

        <View style={styles.about}>
          <Logo size={28} />
          <Wordmark size={16} />
          <Body small soft>Version {APP_VERSION}</Body>
        </View>
      </Screen>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  profile: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  about: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 30, opacity: 0.8 },
});
