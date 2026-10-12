import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Button, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Line } from 'react-native-svg';

import { Body, Logo, Wordmark } from '@/components/ui';
import { usePalette } from '@/hooks';
import { api } from '@/services/api';
import { DEMO_URL, isDemo } from '@/demo/demo';
import { findServer, phoneAddress } from '@/services/discover';
import { sessionActions, useAppDispatch, useAppSelector } from '@/store';
import { APP_VERSION, BRAND, fonts } from '@/theme';

/** Faint blueprint grid behind the brand panel. */
function Grid() {
  const lines = [];
  for (let i = 0; i < 40; i++) {
    lines.push(<Line key={`v${i}`} x1={i * 28} x2={i * 28} y1={0} y2={800} stroke={BRAND.navyLine} strokeWidth={i % 5 ? 0.6 : 1.2} />);
    lines.push(<Line key={`h${i}`} y1={i * 28} y2={i * 28} x1={0} x2={1200} stroke={BRAND.navyLine} strokeWidth={i % 5 ? 0.6 : 1.2} />);
  }
  return <Svg width="100%" height="100%" style={StyleSheet.absoluteFill} pointerEvents="none">{lines}</Svg>;
}

export default function Login() {
  const p = usePalette();
  const dispatch = useAppDispatch();
  const params = useLocalSearchParams<{ server?: string }>();
  const serverUrl = useAppSelector((s) => s.session.serverUrl);
  const [server, setServer] = useState(serverUrl);
  const [editServer, setEditServer] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState<{ ok: boolean; text: string } | null>(null);
  const [searching, setSearching] = useState(false);
  const searched = React.useRef(false);

  useEffect(() => {
    if (params.server) {
      setServer(params.server);
      test(params.server);
    } else test(serverUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.server]);

  async function test(url = server, allowSearch = true): Promise<boolean> {
    dispatch(sessionActions.setServer({ serverUrl: url.trim() }));
    setCheck({ ok: true, text: 'Looking for the server…' });
    try {
      const h = await api.health();
      const robots: any[] = Object.values(h.robots ?? {});
      const r = robots.find((x) => x.online) ?? robots[0];
      setCheck({ ok: true, text: `${h.site ?? 'Server'} found${r ? `, robot ${r.online ? 'online' : 'offline'}` : ''}` });
      setEditServer(false);
      return true;
    } catch {
      if (allowSearch && Platform.OS !== 'web' && !searched.current) {
        searched.current = true;
        return !!(await autoFind());
      }
      setCheck({ ok: false, text: 'Server not found. On the PC run connect_phone.bat, keep the phone on the same Wi-Fi, then tap Find automatically.' });
      setEditServer(true);
      return false;
    }
  }

  async function autoFind(): Promise<string | null> {
    setSearching(true);
    setCheck({ ok: true, text: 'Searching your Wi-Fi for the Raqib server…' });
    try {
      const f = await findServer({
        known: [server, serverUrl].filter((u) => !isDemo(u)),
        onProgress: (n, total) => { if (n % 16 === 0) setCheck({ ok: true, text: `Searching your Wi-Fi for the Raqib server… ${Math.round((n / total) * 100)}%` }); },
      });
      if (f) {
        setServer(f.url);
        return (await test(f.url, false)) ? f.url : null;
      }
      const ip = await phoneAddress();
      setCheck({ ok: false, text: ip
        ? `No server found. This phone is ${ip}, so the PC's address must start with ${ip.split('.').slice(0, 3).join('.')}. On the PC run connect_phone.bat, then tap Find again.`
        : 'No server found. Connect the phone to the same Wi-Fi as the PC (not mobile data), run connect_phone.bat on the PC, then tap Find again.' });
      setEditServer(true);
      return null;
    } finally {
      setSearching(false);
    }
  }

  async function tryDemo() {
    setServer(DEMO_URL);
    setUsername('admin');
    setPassword('admin123');
    setEditServer(false);
    dispatch(sessionActions.setServer({ serverUrl: DEMO_URL, robotId: 'robot01' }));
    setCheck({ ok: true, text: 'Demo robot inside this phone' });
    try {
      const r = await api.login('admin', 'admin123');
      dispatch(sessionActions.loggedIn({ token: r.access_token, username: r.username, role: r.role, name: r.name }));
    } catch (e: any) {
      setCheck({ ok: false, text: e.message });
    }
  }

  async function signIn(foundUrl?: string) {
    const retried = foundUrl != null;
    setBusy(true);
    dispatch(sessionActions.setServer({ serverUrl: (foundUrl ?? server).trim() }));
    try {
      const r = await api.login(username.trim(), password);
      dispatch(sessionActions.loggedIn({ token: r.access_token, username: r.username, role: r.role, name: r.name }));
    } catch (e: any) {
      if (e.status === 0 && !retried && Platform.OS !== 'web' && !isDemo(foundUrl ?? server)) {
        setBusy(false);
        searched.current = true;
        const url = await autoFind();
        if (url) return signIn(url);
        return;
      }
      setCheck({ ok: false, text: e.status === 401 ? 'Wrong username or password.' : e.status === 0 ? 'The server did not answer. On the PC run connect_phone.bat, then try again.' : e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: BRAND.navy }}>
      <Grid />
      <SafeAreaView style={{ flex: 1 }}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={styles.wrap} keyboardShouldPersistTaps="handled">
            <View style={styles.brand}>
              <Logo size={76} />
              <Wordmark size={44} color="#FFFFFF" />
              <Text style={styles.tagline}>An AI robot that walks your building, finds energy waste and safety problems, and tells you what to fix.</Text>
            </View>

            <View style={[styles.card, { backgroundColor: p.surface }]}>
              <Text style={{ fontFamily: fonts.display, fontSize: 22, color: p.ink, letterSpacing: -0.4 }}>Sign in</Text>
              <TextInput mode="outlined" label="Username" value={username} onChangeText={setUsername} autoCapitalize="none"
                autoCorrect={false} left={<TextInput.Icon icon="account-outline" />} />
              <TextInput mode="outlined" label="Password" value={password} onChangeText={setPassword} secureTextEntry={!show}
                onSubmitEditing={() => signIn()} left={<TextInput.Icon icon="lock-outline" />}
                right={<TextInput.Icon icon={show ? 'eye-off-outline' : 'eye-outline'} onPress={() => setShow(!show)} />} />
              <Button mode="contained" onPress={() => signIn()} loading={busy} disabled={busy || !password || !username}
                contentStyle={{ paddingVertical: 8 }} labelStyle={{ fontFamily: fonts.bodyStrong, fontSize: 16 }}>
                Sign in
              </Button>
              <Button mode="outlined" icon="robot-outline" onPress={tryDemo} disabled={busy}
                contentStyle={{ paddingVertical: 4 }}>
                Try the demo robot (no robot needed)
              </Button>

              <View style={[styles.serverBox, { backgroundColor: p.sunken }]}>
                <View style={styles.serverHead}>
                  <MaterialCommunityIcons name={check?.ok === false ? 'lan-disconnect' : 'lan-connect'} size={18}
                    color={check?.ok === false ? p.danger : p.ok} />
                  <Body small style={{ flex: 1, color: check?.ok === false ? p.danger : p.inkSoft }} numberOfLines={2}>
                    {check?.text ?? server}
                  </Body>
                  <Pressable onPress={() => setEditServer(!editServer)} hitSlop={8}>
                    <Text style={{ fontFamily: fonts.bodyStrong, color: p.primary, fontSize: 13 }}>{editServer ? 'Done' : 'Change'}</Text>
                  </Pressable>
                </View>
                {editServer ? (
                  <View style={{ gap: 6, marginTop: 8 }}>
                    <TextInput mode="outlined" dense label="Server address" value={server} onChangeText={setServer}
                      autoCapitalize="none" autoCorrect={false} keyboardType="url" onBlur={() => test(server, false)} />
                    {Platform.OS !== 'web' ? (
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                        <Button icon="radar" mode="contained-tonal" compact loading={searching} disabled={searching} onPress={() => autoFind()}>
                          Find automatically
                        </Button>
                        <Button icon="qrcode-scan" mode="text" compact onPress={() => router.push('/scan')}>
                          Scan the code on the PC
                        </Button>
                      </View>
                    ) : null}
                    <Body small soft>On the PC running the server, open {server.replace(/:\d+$/, '')}:8000/connect to see a QR code.</Body>
                  </View>
                ) : null}
              </View>
            </View>

            <Text style={styles.footer}>Raqib {APP_VERSION}</Text>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 20, paddingTop: 40, maxWidth: 460, width: '100%', alignSelf: 'center', flexGrow: 1 },
  brand: { alignItems: 'flex-start', gap: 10, marginBottom: 28 },
  tagline: { color: '#B8C3E6', fontFamily: fonts.body, fontSize: 16, lineHeight: 23, maxWidth: 380 },
  card: { borderRadius: 24, padding: 20, gap: 12 },
  serverBox: { borderRadius: 14, padding: 12, marginTop: 4 },
  serverHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  footer: { color: '#6E7BA6', fontFamily: fonts.body, fontSize: 12, textAlign: 'center', marginTop: 24 },
});
