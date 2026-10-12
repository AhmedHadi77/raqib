import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router, useFocusEffect } from 'expo-router';
import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { Body, Card, Chip, EmptyState, Pill } from '@/components/ui';
import { usePalette } from '@/hooks';
import { api } from '@/services/api';
import { fonts, ZONE_LABEL } from '@/theme';
import type { ReportListItem } from '@/types';

type Filter = 'all' | 'issues' | 'clear';

function dayLabel(ts: number) {
  const d = new Date(ts * 1000);
  const today = new Date();
  const y = new Date(Date.now() - 86400000);
  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === y.toDateString()) return 'Yesterday';
  return d.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
}

export default function Reports() {
  const p = usePalette();
  const [items, setItems] = useState<ReportListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.reports());
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const shown = useMemo(
    () => items.filter((r) => (filter === 'all' ? true : filter === 'issues' ? !r.compliant : r.compliant)),
    [items, filter],
  );
  const issues = items.filter((r) => !r.compliant).length;

  const rows: ({ kind: 'day'; label: string } | { kind: 'item'; r: ReportListItem })[] = [];
  let last = '';
  for (const r of shown) {
    const label = dayLabel(r.created);
    if (label !== last) {
      rows.push({ kind: 'day', label });
      last = label;
    }
    rows.push({ kind: 'item', r });
  }

  const Stat = ({ n, label, color }: { n: number; label: string; color: string }) => (
    <View style={{ flex: 1, gap: 2 }}>
      <Text style={{ fontFamily: fonts.numeric, fontSize: 28, color, letterSpacing: -0.6 }}>{n}</Text>
      <Body small soft>{label}</Body>
    </View>
  );

  return (
    <FlatList
      style={{ backgroundColor: p.paper }}
      contentContainerStyle={styles.wrap}
      data={rows}
      keyExtractor={(row, i) => (row.kind === 'day' ? `d${i}` : row.r.id)}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={p.primary} />}
      ListHeaderComponent={
        <View style={{ marginBottom: 4 }}>
          <Card style={styles.summary}>
            <Stat n={items.length} label="Inspections" color={p.ink} />
            <View style={[styles.vr, { backgroundColor: p.line }]} />
            <Stat n={issues} label="Need action" color={issues ? p.amber : p.ok} />
            <View style={[styles.vr, { backgroundColor: p.line }]} />
            <Stat n={items.length - issues} label="All clear" color={p.ok} />
          </Card>
          <View style={styles.chips}>
            <Chip label="All" active={filter === 'all'} onPress={() => setFilter('all')} />
            <Chip label="Need action" active={filter === 'issues'} onPress={() => setFilter('issues')} />
            <Chip label="All clear" active={filter === 'clear'} onPress={() => setFilter('clear')} />
          </View>
          {error ? <Body small style={{ color: p.danger, marginTop: 8 }}>{error}</Body> : null}
        </View>
      }
      ListEmptyComponent={
        loading ? null : (
          <EmptyState icon="clipboard-search-outline" title={items.length ? 'Nothing in this filter' : 'No reports yet'}
            body="Ask the assistant to inspect a room, for example “Inspect the IoT Lab”. Every inspection is saved here with photos." />
        )
      }
      renderItem={({ item: row }) =>
        row.kind === 'day' ? (
          <Text style={{ fontFamily: fonts.heading, fontSize: 14, color: p.inkSoft, marginTop: 18, marginBottom: 8 }}>{row.label}</Text>
        ) : (
          <Card onPress={() => router.push(`/report/${row.r.id}`)} style={[styles.item]} radius={14}>
            <View style={[styles.bar, { backgroundColor: row.r.compliant ? p.ok : p.amber }]} />
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={{ fontFamily: fonts.heading, fontSize: 16, color: p.ink }} numberOfLines={1}>
                {row.r.zones.map(ZONE_LABEL).join(', ') || 'Inspection'}
              </Text>
              <Body small soft numberOfLines={1}>
                {new Date(row.r.created * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}, {row.r.request}
              </Body>
            </View>
            <Pill small level={row.r.compliant ? 'ok' : 'warn'} label={row.r.compliant ? 'Clear' : 'Findings'} />
            <MaterialCommunityIcons name="chevron-right" size={20} color={p.inkFaint} />
          </Card>
        )
      }
    />
  );
}

const styles = StyleSheet.create({
  wrap: { padding: 16, paddingBottom: 40, width: '100%', maxWidth: 860, alignSelf: 'center' },
  summary: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 14, paddingHorizontal: 16 },
  vr: { width: StyleSheet.hairlineWidth, alignSelf: 'stretch' },
  chips: { flexDirection: 'row', gap: 8, marginTop: 14 },
  item: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8, overflow: 'hidden', paddingLeft: 18 },
  bar: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 4 },
});
