import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Stack, useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Image, Platform, StyleSheet, Text, View } from 'react-native';
import { Button, Snackbar } from 'react-native-paper';

import { Body, Card, H1, H2, Pill, Screen, Section } from '@/components/ui';
import { usePalette } from '@/hooks';
import { api, authUrl } from '@/services/api';
import { exportHtmlAsPdf } from '@/services/pdf';
import { tts } from '@/services/tts';
import { fonts, levelColors, levelOf, pretty, ZONE_LABEL } from '@/theme';
import type { Anomaly, InspectionReport, ZoneInspection } from '@/types';

const SEV_LEVEL: Record<Anomaly['severity'], 'alert' | 'warn' | 'idle'> = {
  critical: 'alert', high: 'alert', medium: 'warn', low: 'idle',
};

function Fact({ label, value, level }: { label: string; value: string; level?: string | null }) {
  const p = usePalette();
  const c = levelColors(p, levelOf(level ?? undefined));
  return (
    <View style={[styles.fact, { borderColor: p.line }]}>
      <Body small soft>{label}</Body>
      <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 15, color: level ? c.fg : p.ink }}>{value}</Text>
    </View>
  );
}

function ZoneBlock({ z }: { z: ZoneInspection }) {
  const p = usePalette();
  const e = z.environment;
  return (
    <Card style={{ marginBottom: 14, padding: 0, overflow: 'hidden' }}>
      {z.image_file ? <Image source={{ uri: authUrl(`/images/${z.image_file}`) }} style={styles.img} /> : null}
      <View style={{ padding: 14, gap: 10 }}>
        <View style={styles.zoneHead}>
          <H2 style={{ fontSize: 19, flex: 1 }}>{ZONE_LABEL(z.zone)}</H2>
          <Pill level={z.compliant ? 'ok' : 'warn'} label={z.compliant ? 'Compliant' : `${z.anomalies.length} findings`} />
        </View>
        <View style={styles.facts}>
          {z.vision ? <Fact label="People" value={String(z.vision.occupants)} /> : null}
          {e ? <Fact label="Temperature" value={`${e.temperature_c.toFixed(1)} °C`} level={z.comfort_verdict} /> : null}
          {e ? <Fact label="Humidity" value={`${e.humidity_pct.toFixed(0)} %`} level={z.comfort_verdict} /> : null}
          {e ? <Fact label="Air quality" value={`AQI ${Math.round(e.aqi ?? 0)}`} level={z.gas_verdict} /> : null}
          {z.audio ? <Fact label="Sound" value={z.audio.title || pretty(z.audio.label)} /> : null}
          <Fact label="Energy" value={z.energy_status === 'WASTE' ? 'Waste found' : 'OK'} level={z.energy_status === 'WASTE' ? 'WASTE' : 'ok'} />
        </View>
        {z.anomalies.length ? (
          <View style={{ gap: 6 }}>
            {z.anomalies.map((a, i) => {
              const c = levelColors(p, SEV_LEVEL[a.severity]);
              return (
                <View key={i} style={[styles.finding, { backgroundColor: c.bg }]}>
                  <MaterialCommunityIcons name={a.severity === 'critical' || a.severity === 'high' ? 'alert-octagon' : 'alert-circle-outline'}
                    size={18} color={c.fg} style={{ marginTop: 1 }} />
                  <Body small style={{ flex: 1 }}>{a.description}</Body>
                </View>
              );
            })}
          </View>
        ) : (
          <Body soft>No issues found in this room.</Body>
        )}
        {z.vision?.needs_human_review ? (
          <Body small style={{ color: p.amber }}>The vision result disagrees with the sensors — please check the photo.</Body>
        ) : null}
        {z.vision?.description ? <Body small soft>{z.vision.description}</Body> : null}
      </View>
    </Card>
  );
}

function spoken(r: InspectionReport) {
  const parts = r.zones.map((z) =>
    z.compliant ? `${ZONE_LABEL(z.zone)} is all clear.`
      : `${ZONE_LABEL(z.zone)} has ${z.anomalies.length} finding${z.anomalies.length > 1 ? 's' : ''}: ` +
        z.anomalies.map((a) => a.description.replace(/\s*\([^)]*\)/g, '')).join('; ') + '.');
  const top = r.zones.flatMap((z) => z.recommended_actions).find((a) => a.priority === 'Critical' || a.priority === 'High');
  return parts.join(' ').replace(/°C/g, ' degrees').replace(/% RH/g, ' percent humidity') + (top ? ` Most urgent: ${top.action}` : '');
}

export default function ReportScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const p = usePalette();
  const [r, setR] = useState<InspectionReport | null>(null);
  const [err, setErr] = useState('');
  const [exporting, setExporting] = useState(false);
  const [snack, setSnack] = useState('');

  useEffect(() => {
    api.report(String(id)).then(setR).catch((e) => setErr(e.message));
  }, [id]);

  const exportPdf = async () => {
    setExporting(true);
    try {
      const msg = await exportHtmlAsPdf(await api.reportHtml(String(id)), 'Share audit report');
      if (msg) setSnack(msg);
    } catch (e: any) {
      setSnack(e?.message ?? String(e));
    } finally {
      setExporting(false);
    }
  };

  if (err) return <Screen><Body style={{ color: p.danger, marginTop: 24 }}>{err}</Body></Screen>;
  if (!r) return <Screen><ActivityIndicator style={{ marginTop: 48 }} color={p.primary} /></Screen>;

  const actions = r.zones.flatMap((z) => z.recommended_actions.map((a) => ({ ...a, zone: z.zone })));
  const order: Record<string, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  actions.sort((a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9));
  const findings = r.zones.reduce((n, z) => n + z.anomalies.length, 0);

  return (
    <>
      <Stack.Screen options={{ title: 'Audit report' }} />
      <Screen>
        <Body small soft>
          {new Date(r.created * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}, by {r.robot_id}
        </Body>
        <H1 style={{ marginTop: 4 }}>{r.zones.map((z) => ZONE_LABEL(z.zone)).join(' & ')}</H1>
        <Body soft style={{ marginTop: 4 }}>“{r.request}”</Body>
        <View style={styles.headRow}>
          <Pill level={findings ? 'warn' : 'ok'} label={findings ? `${findings} findings` : 'All rooms compliant'} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button mode="outlined" icon="volume-high" onPress={() => tts.speak(spoken(r))}>Listen</Button>
            <Button mode="contained" icon="file-pdf-box" onPress={exportPdf} loading={exporting} disabled={exporting}>
              Export PDF
            </Button>
          </View>
        </View>

        <Section title="Rooms">{r.zones.map((z) => <ZoneBlock key={z.id} z={z} />)}</Section>

        <Section title="Recommended actions" style={{ marginTop: 6 }}>
          <Card style={{ gap: 12 }}>
            {actions.length === 0 ? <Body soft>Nothing to do — every room passed.</Body> : null}
            {actions.map((a, i) => {
              const lvl = a.priority === 'Critical' || a.priority === 'High' ? 'alert' : a.priority === 'Medium' ? 'warn' : 'idle';
              const c = levelColors(p, lvl);
              return (
                <View key={i} style={styles.action}>
                  <View style={[styles.prio, { backgroundColor: c.bg }]}>
                    <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 12, color: c.fg }}>{a.priority}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Body>{a.action}</Body>
                    <Body small soft>{a.category} · {ZONE_LABEL(a.zone)}</Body>
                  </View>
                </View>
              );
            })}
          </Card>
        </Section>
      </Screen>
      <Snackbar visible={!!snack} onDismiss={() => setSnack('')} duration={4000}>{snack}</Snackbar>
    </>
  );
}

const styles = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 14, gap: 10, flexWrap: 'wrap' },
  img: { width: '100%', aspectRatio: 4 / 3 },
  zoneHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  fact: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6, minWidth: 96 },
  finding: { flexDirection: 'row', gap: 8, padding: 10, borderRadius: 10 },
  action: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  prio: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, minWidth: 64, alignItems: 'center', marginTop: 2 },
});
