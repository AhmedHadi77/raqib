import { MaterialCommunityIcons } from '@expo/vector-icons';
import { router } from 'expo-router';
import React, { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { usePalette } from '@/hooks';
import { alertActions, useAppDispatch, useAppSelector } from '@/store';
import { fonts } from '@/theme';

export default function AlertBanner() {
  const p = usePalette();
  const insets = useSafeAreaInsets();
  const dispatch = useAppDispatch();
  const top = useAppSelector((s) => s.alerts.items[0]);

  useEffect(() => {
    if (!top) return;
    const t = setTimeout(() => dispatch(alertActions.dismiss(top.id)), 9000);
    return () => clearTimeout(t);
  }, [top, dispatch]);

  if (!top) return null;
  const bg = top.level === 'alert' ? p.danger : top.level === 'ok' ? p.ok : '#B87300';
  return (
    <View pointerEvents="box-none" style={[styles.wrap, { top: insets.top + 8 }]}>
      <Pressable onPress={() => { dispatch(alertActions.dismiss(top.id)); if (top.route) router.push(top.route as any); else if (top.reportId) router.push(`/report/${top.reportId}`); }} style={[styles.card, { backgroundColor: bg }]}
        accessibilityRole="alert">
        <MaterialCommunityIcons name={top.level === 'alert' ? 'alert-octagon' : top.level === 'ok' ? 'check-circle' : 'alert'} size={22} color="#fff" />
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>{top.title}</Text>
          <Text style={styles.body}>{top.body}</Text>
        </View>
        <MaterialCommunityIcons name="close" size={18} color="#ffffffcc" />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: 12, right: 12, alignItems: 'center' },
  card: {
    width: '100%', maxWidth: 560, flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16,
    shadowColor: '#000', shadowOpacity: 0.25, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 8,
  },
  title: { color: '#fff', fontFamily: fonts.heading, fontSize: 15 },
  body: { color: '#fff', fontFamily: fonts.body, fontSize: 13.5, marginTop: 2, opacity: 0.95 },
});
