// Always-visible emergency stop. Any signed-in role may press it.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import React, { useState } from 'react';
import { Platform, Pressable, StyleSheet, Text } from 'react-native';

import { api } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts } from '@/theme';

export default function EStopButton({ compact = false }: { compact?: boolean }) {
  const robotId = useAppSelector((s) => s.session.robotId);
  const state = useAppSelector((s) => s.robot.telemetry?.state);
  const [busy, setBusy] = useState(false);
  const latched = state === 'EMERGENCY_STOP';

  const press = async () => {
    if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
    setBusy(true);
    try {
      if (latched) await api.reset(robotId);
      else await api.estop(robotId);
    } catch {
      // server unreachable: the robot's own 10 s watchdog puts it in safe hold anyway
    } finally {
      setBusy(false);
    }
  };

  return (
    <Pressable onPress={press} disabled={busy} accessibilityRole="button"
      accessibilityLabel={latched ? 'Release emergency stop' : 'Emergency stop'}
      style={({ pressed }) => [styles.btn, compact && styles.compact, latched && styles.latched, pressed && { transform: [{ scale: 0.96 }] }]}>
      <MaterialCommunityIcons name={latched ? 'lock-open-variant' : 'octagon'} size={compact ? 16 : 20} color="#fff" />
      <Text style={[styles.txt, compact && { fontSize: 14 }]}>{latched ? 'Release stop' : busy ? 'Stopping…' : 'Stop'}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C62828', borderRadius: 999,
    paddingVertical: 14, paddingHorizontal: 22, borderWidth: 3, borderColor: '#F2B437',
    shadowColor: '#000', shadowOpacity: 0.3, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 8,
  },
  compact: { paddingVertical: 8, paddingHorizontal: 14, borderWidth: 2 },
  latched: { backgroundColor: '#5D4037' },
  txt: { color: '#fff', fontFamily: fonts.heading, fontSize: 18, letterSpacing: 0.3 },
});
