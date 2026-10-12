// AI settings (admin): connect Gemini, OpenAI or Ollama so the robot understands any wording and its photos.
// The key is sent once to your own server, saved in backend/.env and never shown again in full.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { Button, Snackbar, TextInput } from 'react-native-paper';

import { Body, Card, Pill, Screen, Section } from '@/components/ui';
import { usePalette } from '@/hooks';
import { api } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts } from '@/theme';
import type { AiSettings } from '@/types';

type Provider = AiSettings['provider'];
type IconName = React.ComponentProps<typeof MaterialCommunityIcons>['name'];

const OPTIONS: { id: Provider; title: string; tag: string; level: 'ok' | 'warn' | 'idle'; icon: IconName; body: string; link?: string; linkText?: string }[] = [
  { id: 'gemini', title: 'Google Gemini', tag: 'Free key', level: 'ok', icon: 'google',
    body: 'Recommended. Understands any wording and what is in each photo. The free tier is enough for a school.',
    link: 'https://aistudio.google.com/apikey', linkText: 'Get a free key (Google account)' },
  { id: 'openai', title: 'OpenAI GPT-4o', tag: 'Paid', level: 'warn', icon: 'creation',
    body: 'Most accurate. Costs a few cents a day in normal use.',
    link: 'https://platform.openai.com/api-keys', linkText: 'Get a key' },
  { id: 'ollama', title: 'Ollama on this PC', tag: 'Free, offline', level: 'ok', icon: 'desktop-tower-monitor',
    body: 'Runs on the server PC with no internet. Needs a PC with 16 GB RAM (a graphics card helps).',
    link: 'https://ollama.com/download', linkText: 'Download Ollama' },
  { id: 'none', title: 'Built-in only', tag: 'Offline', level: 'idle', icon: 'robot-outline',
    body: 'Knows the listed commands and any chain of them. Replies with suggestions to anything else. Cannot understand photos.' },
];

const NICE = (s?: string) => !s ? '…' : s.startsWith('local:') ? 'Whisper on the server' : s === 'rules' ? 'Built-in' : s === 'mock' ? 'Simulator only' : s === 'none' ? 'Off' : s.replace(/^llm:/, '');

export default function AiScreen() {
  const p = usePalette();
  const role = useAppSelector((s) => s.session.role);
  const [cfg, setCfg] = useState<AiSettings | null>(null);
  const [provider, setProvider] = useState<Provider>('gemini');
  const [key, setKey] = useState('');
  const [show, setShow] = useState(false);
  const [ollama, setOllama] = useState({ model: '', vision: '', url: '' });
  const [photos, setPhotos] = useState(true);
  const [busy, setBusy] = useState<'' | 'save' | 'test'>('');
  const [test, setTest] = useState<Awaited<ReturnType<typeof api.testAi>> | null>(null);
  const [snack, setSnack] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    api.aiSettings().then((c) => {
      setCfg(c);
      setProvider(c.provider === 'none' && !c.google_api_key ? 'gemini' : c.provider);
      setOllama({ model: c.ollama_model, vision: c.ollama_vision_model, url: c.ollama_base_url });
    }).catch((e) => setErr(e.message));
  }, []);

  if (role !== 'admin') return <Screen><Body style={{ marginTop: 24 }}>Only administrators can change the AI settings.</Body></Screen>;
  if (err && !cfg) return <Screen><Body style={{ color: p.danger, marginTop: 24 }}>{err}</Body></Screen>;
  if (!cfg) return <Screen><ActivityIndicator style={{ marginTop: 48 }} color={p.primary} /></Screen>;

  const existing = provider === 'gemini' ? cfg.google_api_key : provider === 'openai' ? cfg.openai_api_key : null;
  const needsKey = (provider === 'gemini' || provider === 'openai') && !existing && !key.trim();
  const missingPkg = provider !== 'none' && cfg.packages[provider] === false;
  const opt = OPTIONS.find((o) => o.id === provider)!;

  const save = async () => {
    setBusy('save');
    setErr('');
    setTest(null);
    try {
      const body: Record<string, any> = { provider, use_for_vision: photos };
      if (provider === 'gemini' && key.trim()) body.google_api_key = key.trim();
      if (provider === 'openai' && key.trim()) body.openai_api_key = key.trim();
      if (provider === 'ollama') Object.assign(body, { ollama_model: ollama.model, ollama_vision_model: ollama.vision, ollama_base_url: ollama.url });
      const c = await api.saveAiSettings(body);
      setCfg(c);
      setKey('');
      setSnack(c.saved === false ? 'Applied, but backend/.env could not be written: it will reset when the server restarts.' : 'Saved and switched on. Testing it now…');
      if (provider !== 'none') await runTest();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy('');
    }
  };
  const runTest = async () => {
    setBusy('test');
    try {
      setTest(await api.testAi());
    } catch (e: any) {
      setTest({ ok: false, error: e.message });
    } finally {
      setBusy('');
    }
  };

  return (
    <>
      <Screen>
        <Body soft style={{ marginTop: 8 }}>
          Connect an AI model so the robot understands any order in your own words, answers questions about what it sees,
          and spots notes and earpieces during exams.
        </Body>

        <Card tone="sunken" style={{ marginTop: 14, gap: 8 }}>
          <Text style={{ fontFamily: fonts.heading, color: p.ink, fontSize: 15 }}>Working now</Text>
          {[
            ['message-text-outline', 'Understanding orders', NICE(cfg.active.planner)],
            ['image-search-outline', 'Understanding photos', NICE(cfg.active.vision)],
            ['microphone-outline', 'Voice typing', NICE(cfg.active.voice)],
          ].map(([icon, label, v]) => (
            <View key={label} style={styles.row}>
              <MaterialCommunityIcons name={icon as IconName} size={18} color={p.primary} />
              <Body small style={{ flex: 1 }}>{label}</Body>
              <Body small strong>{v}</Body>
            </View>
          ))}
        </Card>

        <Section title="AI model">
          <View style={{ gap: 10 }}>
            {OPTIONS.map((o) => {
              const on = provider === o.id;
              return (
                <Pressable key={o.id} onPress={() => { setProvider(o.id); setKey(''); setTest(null); setErr(''); }} accessibilityRole="radio"
                  accessibilityState={{ selected: on }}
                  style={[styles.option, { borderColor: on ? p.primary : p.line, backgroundColor: on ? p.primarySoft : p.surface }]}>
                  <MaterialCommunityIcons name={o.icon} size={22} color={on ? p.primary : p.inkSoft} />
                  <View style={{ flex: 1, gap: 3 }}>
                    <View style={styles.row}>
                      <Text style={{ fontFamily: fonts.heading, color: p.ink, fontSize: 15.5 }}>{o.title}</Text>
                      <Pill small level={o.level} label={o.tag} />
                      {cfg.provider === o.id ? <Pill small level="ok" icon="check" label="In use" /> : null}
                    </View>
                    <Body small soft>{o.body}</Body>
                  </View>
                  <MaterialCommunityIcons name={on ? 'radiobox-marked' : 'radiobox-blank'} size={22} color={on ? p.primary : p.inkFaint} />
                </Pressable>
              );
            })}
          </View>
        </Section>

        {provider !== 'none' ? (
          <Section title={provider === 'ollama' ? 'Ollama models' : 'API key'}>
            <Card style={{ gap: 10 }}>
              {provider === 'ollama' ? (
                <>
                  <Body small soft>On the server PC run: ollama pull {ollama.model || 'llama3.1'} and ollama pull {ollama.vision || 'qwen2.5vl'}</Body>
                  <TextInput mode="outlined" dense label="Model for orders" value={ollama.model} onChangeText={(model) => setOllama({ ...ollama, model })} autoCapitalize="none" />
                  <TextInput mode="outlined" dense label="Model for photos" value={ollama.vision} onChangeText={(vision) => setOllama({ ...ollama, vision })} autoCapitalize="none" />
                  <TextInput mode="outlined" dense label="Ollama address" value={ollama.url} onChangeText={(url) => setOllama({ ...ollama, url })} autoCapitalize="none" keyboardType="url" />
                </>
              ) : (
                <>
                  <Body small soft>{cfg.help[provider]}</Body>
                  <TextInput mode="outlined" dense label={existing ? `Saved key ${existing}. Paste a new one to replace it` : 'Paste your API key'}
                    value={key} onChangeText={setKey} secureTextEntry={!show} autoCapitalize="none" autoCorrect={false}
                    right={<TextInput.Icon icon={show ? 'eye-off' : 'eye'} onPress={() => setShow(!show)} />} />
                </>
              )}
              {opt.link ? (
                <Button compact icon="open-in-new" style={{ alignSelf: 'flex-start' }} onPress={() => Linking.openURL(opt.link!)}>{opt.linkText}</Button>
              ) : null}
              <Pressable onPress={() => setPhotos(!photos)} style={styles.row} accessibilityRole="checkbox" accessibilityState={{ checked: photos }}>
                <MaterialCommunityIcons name={photos ? 'checkbox-marked' : 'checkbox-blank-outline'} size={22} color={photos ? p.primary : p.inkSoft} />
                <Body small style={{ flex: 1 }}>Also use it to understand photos (needed with the real robot)</Body>
              </Pressable>
            </Card>
          </Section>
        ) : null}

        {missingPkg ? (
          <Card tone="sunken" style={[styles.row, { marginTop: 14 }]}>
            <MaterialCommunityIcons name="alert-outline" size={18} color={p.amber} />
            <Body small style={{ flex: 1 }}>The server needs the {opt.title} package first. Run upgrade.bat on the server PC once, then come back.</Body>
          </Card>
        ) : null}
        {err ? <Body small style={{ color: p.danger, marginTop: 12 }}>{err}</Body> : null}

        <View style={{ flexDirection: 'row', gap: 10, marginTop: 20 }}>
          <Button mode="contained" icon="content-save-outline" style={{ flex: 1 }} contentStyle={{ paddingVertical: 4 }}
            onPress={save} loading={busy === 'save'} disabled={!!busy || needsKey || missingPkg}>
            Save and switch on
          </Button>
          {cfg.provider !== 'none' ? (
            <Button mode="outlined" icon="flask-outline" onPress={runTest} loading={busy === 'test'} disabled={!!busy}>Test</Button>
          ) : null}
        </View>

        {test ? (
          <Card style={{ marginTop: 14, gap: 6, borderColor: test.ok ? p.ok : p.danger }}>
            <View style={styles.row}>
              <MaterialCommunityIcons name={test.ok ? 'check-circle' : 'close-circle'} size={20} color={test.ok ? p.ok : p.danger} />
              <Text style={{ fontFamily: fonts.heading, color: p.ink, fontSize: 15, flex: 1 }}>
                {test.ok ? `Working (${test.seconds}s)` : 'Not working yet'}
              </Text>
            </View>
            {test.ok ? (
              <>
                <Body small soft>Asked: “{test.sample}”</Body>
                <Body small>{test.plan ? `Planned: ${test.plan}` : test.reply ? `Replied: ${test.reply}` : 'No plan returned.'}</Body>
              </>
            ) : <Body small>{test.error}</Body>}
          </Card>
        ) : null}

        <Body small soft style={{ marginTop: 18 }}>
          The key is stored only on your server (backend/.env) and never shown again in full. Photos are sent to the AI
          provider you choose; choose Ollama to keep everything on your own PC.
        </Body>
      </Screen>
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={4500}>{snack}</Snackbar>
    </>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, borderWidth: 1.5 },
});
