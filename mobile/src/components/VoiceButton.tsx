// Tap to talk to the robot. Tap again (or just stop talking) to send.
// While listening, a panel shows what was heard; the reply is spoken back and shown in the Assistant.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useIsFocused } from 'expo-router';
import * as Haptics from 'expo-haptics';
import React, { useEffect, useRef } from 'react';
import { ActivityIndicator, Animated, Easing, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { Portal } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { usePalette } from '@/hooks';
import { ask } from '@/services/assistant';
import { useVoiceInput } from '@/services/useVoiceInput';
import { useAppSelector } from '@/store';
import { BRAND, fonts } from '@/theme';

export default function VoiceButton({ size = 56, onText, zoneHint, panelOffset = 96, disabled, showProgress = true }: {
  size?: number;
  showProgress?: boolean;
  onText?: (t: string) => void;
  zoneHint?: string | null;
  panelOffset?: number;
  disabled?: boolean;
}) {
  const p = usePalette();
  const insets = useSafeAreaInsets();
  const busy = useAppSelector((s) => s.chat.busy);
  const progress = useAppSelector((s) => s.chat.progress);
  const voiceTurn = useAppSelector((s) => s.chat.voiceTurn);
  const v = useVoiceInput((t) => (onText ? onText(t) : ask(t, { voice: true, zoneHint })));
  const ring = useRef(new Animated.Value(0)).current;
  const listening = v.state === 'listening';

  useEffect(() => {
    if (!listening) return;
    const loop = Animated.loop(Animated.timing(ring, { toValue: 1, duration: 1400, easing: Easing.out(Easing.quad), useNativeDriver: Platform.OS !== 'web' }));
    loop.start();
    return () => {
      loop.stop();
      ring.setValue(0);
    };
  }, [listening, ring]);

  useEffect(() => {
    if (!v.error) return;
    const t = setTimeout(v.clearError, 6000);
    return () => clearTimeout(t);
  }, [v.error, v.clearError]);

  const press = () => {
    if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    if (listening) v.stop();
    else if (v.state === 'idle') v.start();
  };

  const focused = useIsFocused();
  const showPanel = focused && (listening || v.state === 'transcribing' || !!v.error || (showProgress && busy && voiceTurn));
  const bg = listening ? p.danger : p.primary;
  const level = 1 + v.level * 0.35;

  return (
    <>
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        {listening ? (
          <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, {
            borderRadius: size, backgroundColor: bg,
            opacity: ring.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0] }),
            transform: [{ scale: ring.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9] }) }],
          }]} />
        ) : null}
        <Pressable onPress={press} disabled={disabled || v.state === 'transcribing' || (busy && !listening)}
          accessibilityRole="button" accessibilityLabel={listening ? 'Stop listening and send' : 'Speak a command'}
          style={({ pressed }) => [{
            width: size, height: size, borderRadius: size / 2, backgroundColor: bg, alignItems: 'center', justifyContent: 'center',
            opacity: disabled ? 0.4 : 1, transform: [{ scale: pressed ? 0.94 : listening ? level : 1 }],
          }, styles.shadow]}>
          {v.state === 'transcribing' ? (
            <ActivityIndicator color={p.onPrimary} />
          ) : (
            <MaterialCommunityIcons name={listening ? 'stop' : 'microphone'} size={size * 0.46} color="#fff" />
          )}
        </Pressable>
      </View>

      {showPanel ? (
        <Portal>
          <View pointerEvents="box-none" style={[styles.panelWrap, { bottom: panelOffset + insets.bottom }]}>
            <View style={[styles.panel, { backgroundColor: BRAND.navy }]}>
              <MaterialCommunityIcons
                name={v.error ? 'microphone-off' : listening ? 'waveform' : 'robot-outline'}
                size={22} color={v.error ? '#FF8A8A' : BRAND.cyan} />
              <View style={{ flex: 1 }}>
                <Text style={styles.panelTitle}>
                  {v.error ? 'Voice not available' : listening ? 'Listening…' : v.state === 'transcribing' ? 'Got it, reading your command…' : 'Working on it'}
                </Text>
                <Text style={styles.panelBody} numberOfLines={3}>
                  {v.error ?? (listening ? v.partial || 'Say a command, for example "check the aircon in Hall B".'
                    : v.state === 'transcribing' ? ' ' : progress || 'Planning…')}
                </Text>
              </View>
              {listening ? (
                <Pressable onPress={v.cancel} hitSlop={8} accessibilityLabel="Cancel">
                  <MaterialCommunityIcons name="close" size={20} color="#B8C3E6" />
                </Pressable>
              ) : null}
            </View>
          </View>
        </Portal>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  shadow: { shadowColor: '#0D1530', shadowOpacity: 0.3, shadowRadius: 10, shadowOffset: { width: 0, height: 5 }, elevation: 6 },
  panelWrap: { position: 'absolute', left: 12, right: 12, alignItems: 'center' },
  panel: {
    width: '100%', maxWidth: 560, flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, paddingHorizontal: 16,
    borderRadius: 18, shadowColor: '#000', shadowOpacity: 0.3, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 10,
  },
  panelTitle: { color: '#fff', fontFamily: fonts.heading, fontSize: 15 },
  panelBody: { color: '#C7D0EE', fontFamily: fonts.body, fontSize: 14, marginTop: 2, lineHeight: 19 },
});
