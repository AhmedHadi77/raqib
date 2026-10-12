import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { ActivityIndicator, Searchbar, SegmentedButtons } from 'react-native-paper';

import TrendChart from '@/components/TrendChart';
import { Body, Card, EmptyState, Pill, Screen, Section } from '@/components/ui';
import { usePalette, usePolling } from '@/hooks';
import { api } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts, levelOf, ZONE_LABEL } from '@/theme';
import type { SearchResponse } from '@/types';

const QUESTIONS = [
  'Rooms where the air quality was unhealthy last month',
  'Has Lecture Hall B been uncomfortably humid this month?',
  'Lights or projector left on in empty rooms',
  'Blocked emergency exits this semester',
  'Over-cooled rooms with the AC running',
];

export default function History() {
  const p = usePalette();
  const robotId = useAppSelector((s) => s.session.robotId);
  const [minutes, setMinutes] = useState('15');
  const hist = usePolling(() => api.history(robotId, Number(minutes)), 10000, [robotId, minutes]);
  const [q, setQ] = useState('');
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const search = async (query?: string) => {
    const text = (query ?? q).trim();
    if (!text) return;
    setQ(text);
    setBusy(true);
    try {
      setRes(await api.search(text));
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const pts = hist.data ?? [];
  const series = (k: 'temperature_c' | 'humidity_pct' | 'aqi' | 'db') => pts.map((h) => ({ ts: h.ts, v: h[k] as number | null }));

  return (
    <Screen>
      <Section
        title="Live trends"
        style={{ marginTop: 4 }}
        action={
          <SegmentedButtons
            density="small"
            value={minutes}
            onValueChange={setMinutes}
            style={{ width: 200 }}
            buttons={[{ value: '15', label: '15m' }, { value: '30', label: '30m' }, { value: '60', label: '1h' }]}
          />
        }
      >
        <Card style={{ gap: 18 }}>
          <TrendChart title="Temperature" unit="°C" points={series('temperature_c')} color={p.danger} band={[22, 26]} />
          <TrendChart title="Humidity" unit="%" points={series('humidity_pct')} color={p.info} band={[40, 60]} decimals={0} />
          <TrendChart title="Air quality index" unit="AQI" points={series('aqi')} color={p.amber} band={[0, 100]} decimals={0} />
          <TrendChart title="Sound level" unit="dB" points={series('db')} color={p.primary} decimals={0} />
          <Body small soft>
            Values follow the robot as it moves, so a jump usually means it entered another room. Green bands show the comfort targets.
          </Body>
        </Card>
      </Section>

      <Section title="Ask about past inspections">
        <Searchbar
          placeholder="e.g. rooms with poor air last week"
          value={q}
          onChangeText={setQ}
          onSubmitEditing={() => search()}
          loading={busy}
          style={{ backgroundColor: p.surface, borderWidth: StyleSheet.hairlineWidth, borderColor: p.line }}
          inputStyle={{ fontFamily: fonts.body }}
        />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }} contentContainerStyle={styles.qs}>
          {QUESTIONS.map((x) => (
            <Pressable key={x} onPress={() => search(x)} style={[styles.q, { backgroundColor: p.surface, borderColor: p.line }]}>
              <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 13, color: p.ink }}>{x}</Text>
            </Pressable>
          ))}
        </ScrollView>
        {error ? <Body small style={{ color: p.danger }}>{error}</Body> : null}
        {busy && !res ? <ActivityIndicator color={p.primary} style={{ marginTop: 20 }} /> : null}
        {res ? (
          <Body small soft style={{ marginVertical: 8 }}>
            {res.results.length} matching records in {res.took_ms} ms
          </Body>
        ) : null}
        {res && res.results.length === 0 ? (
          <EmptyState icon="text-search" title="Nothing matched" body="Try a broader question, or run a few inspections first." />
        ) : null}
        {res?.results.map((h) => {
          const m = h.metadata as Record<string, any>;
          return (
            <Card key={h.id} style={{ marginBottom: 8, gap: 8 }}
              onPress={m.report_id ? () => router.push(`/report/${m.report_id}`) : undefined}>
              <View style={styles.hitHead}>
                <MaterialCommunityIcons name="door" size={18} color={p.primary} />
                <Text style={{ fontFamily: fonts.heading, fontSize: 15.5, color: p.ink, flex: 1 }}>
                  {ZONE_LABEL(String(m.zone))}
                </Text>
                <Body small soft>{String(m.date)}</Body>
              </View>
              <View style={styles.tags}>
                {m.temperature_c > 0 ? (
                  <Pill level={levelOf(m.comfort_verdict)} label={`${Number(m.temperature_c).toFixed(1)} °C · ${Math.round(m.humidity_pct)} %`} />
                ) : null}
                {m.aqi > 0 ? <Pill level={levelOf(m.gas_verdict)} label={`AQI ${Math.round(m.aqi)}`} /> : null}
                {m.energy_status === 'WASTE' ? <Pill level="warn" label="Energy waste" /> : null}
                {m.safety_status === 'HAZARD' ? <Pill level="alert" label="Safety hazard" /> : null}
                {m.seeded ? <Pill label="Demo data" /> : null}
              </View>
              <Body small soft numberOfLines={3}>{h.text.replace(/^Inspection of zone \S+ on [^.]+\.\s*/, '')}</Body>
              {m.report_id ? <Body small style={{ color: p.primary, fontFamily: fonts.bodyStrong }}>Open report</Body> : null}
            </Card>
          );
        })}
        {!res && !busy ? (
          <Body small soft style={{ marginTop: 8 }}>
            Searches every saved inspection by meaning, not just keywords — dates, rooms and problems are understood automatically.
          </Body>
        ) : null}
      </Section>
    </Screen>
  );
}

const styles = StyleSheet.create({
  qs: { gap: 8, paddingVertical: 10 },
  q: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, borderWidth: StyleSheet.hairlineWidth },
  hitHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
});
