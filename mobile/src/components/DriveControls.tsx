// Manual drive controls for the console: 8-way pad, analog joystick and camera pan/tilt pad.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import React, { useRef, useState } from 'react';
import { GestureResponderEvent, PanResponder, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { usePalette } from '@/hooks';
import { Dir, dirToWheels, drive } from '@/services/drive';
import { fonts } from '@/theme';

import type { IconName } from './ui';

const tick = () => {
  if (Platform.OS !== 'web') Haptics.selectionAsync().catch(() => {});
};

function PadKey({ icon, label, onIn, onOut, disabled, size, accent, active }: {
  icon: IconName; label: string; onIn: () => void; onOut?: () => void; disabled?: boolean; size: number; accent?: boolean; active?: boolean;
}) {
  const p = usePalette();
  return (
    <Pressable disabled={disabled} onPressIn={onIn} onPressOut={onOut} accessibilityLabel={label} accessibilityRole="button"
      style={({ pressed }) => [styles.key, {
        width: size, height: size, borderRadius: size * 0.28,
        backgroundColor: pressed || active ? p.primary : accent ? p.console : p.console2,
        borderColor: accent ? p.consoleSoft : p.consoleLine, opacity: disabled ? 0.35 : 1,
      }]}>
      {({ pressed }) => <MaterialCommunityIcons name={icon} size={size * 0.42} color={pressed || active ? '#fff' : p.consoleInk} />}
    </Pressable>
  );
}

/** 3x3 pad: diagonals curve, the middle row spins in place, centre = stop. */
export function DrivePad({ speed, disabled, active }: { speed: number; disabled?: boolean; active?: Dir | null }) {
  const go = (d: Dir) => () => {
    tick();
    const [l, r] = dirToWheels(d, speed);
    drive.set(l, r);
  };
  const stop = () => drive.stop();
  const size = 66;
  const K = (d: Dir, icon: IconName, label: string) => (
    <PadKey icon={icon} label={label} onIn={go(d)} onOut={stop} disabled={disabled} size={size} active={active === d} />
  );
  return (
    <View style={styles.pad}>
      <View style={styles.padRow}>
        {K('fl', 'arrow-top-left', 'Forward left')}
        {K('f', 'arrow-up-bold', 'Forward')}
        {K('fr', 'arrow-top-right', 'Forward right')}
      </View>
      <View style={styles.padRow}>
        {K('l', 'rotate-left', 'Spin left')}
        <PadKey icon="stop" label="Stop" onIn={() => { tick(); drive.stop(); }} disabled={disabled} size={size} accent />
        {K('r', 'rotate-right', 'Spin right')}
      </View>
      <View style={styles.padRow}>
        {K('bl', 'arrow-bottom-left', 'Reverse left')}
        {K('b', 'arrow-down-bold', 'Reverse')}
        {K('br', 'arrow-bottom-right', 'Reverse right')}
      </View>
    </View>
  );
}

/** Analog stick: push to drive, sideways to steer; let go to stop. */
export function Joystick({ speed, disabled, size = 210 }: { speed: number; disabled?: boolean; size?: number }) {
  const p = usePalette();
  const [knob, setKnob] = useState({ x: 0, y: 0 });
  const radius = size / 2 - 34;
  const origin = useRef({ x: 0, y: 0 });

  const update = (dx: number, dy: number) => {
    const d = Math.hypot(dx, dy);
    const k = d > radius ? radius / d : 1;
    const x = dx * k;
    const y = dy * k;
    setKnob({ x, y });
    const fx = x / radius; // right +
    const fy = -y / radius; // forward +
    if (Math.hypot(fx, fy) < 0.12) return drive.set(0.0001, 0.0001);
    const l = Math.max(-1, Math.min(1, fy + fx * 0.75)) * speed;
    const r = Math.max(-1, Math.min(1, fy - fx * 0.75)) * speed;
    drive.set(l, r);
  };
  const release = () => {
    setKnob({ x: 0, y: 0 });
    drive.stop();
  };
  const pr = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e: GestureResponderEvent) => {
        tick();
        origin.current = { x: e.nativeEvent.locationX - size / 2, y: e.nativeEvent.locationY - size / 2 };
        update(origin.current.x, origin.current.y);
      },
      onPanResponderMove: (_e, g) => update(origin.current.x + g.dx, origin.current.y + g.dy),
      onPanResponderRelease: release,
      onPanResponderTerminate: release,
    }),
  ).current;

  return (
    <View style={{ alignItems: 'center', opacity: disabled ? 0.35 : 1 }} pointerEvents={disabled ? 'none' : 'auto'}>
      <View {...pr.panHandlers}
        style={[styles.stickBase, { width: size, height: size, borderRadius: size / 2, backgroundColor: p.console2, borderColor: p.consoleLine }]}>
        {(['chevron-up', 'chevron-down', 'chevron-left', 'chevron-right'] as IconName[]).map((ic, i) => (
          <MaterialCommunityIcons key={ic} name={ic} size={22} color={p.consoleSoft} pointerEvents="none"
            style={[styles.stickArrow, [{ top: 8 }, { bottom: 8 }, { left: 8 }, { right: 8 }][i]]} />
        ))}
        <View pointerEvents="none" style={[styles.stickRing, { width: radius * 2, height: radius * 2, borderRadius: radius, borderColor: p.consoleLine }]} />
        <View pointerEvents="none" style={[styles.knob, {
          backgroundColor: knob.x || knob.y ? p.primary : p.consoleInk,
          transform: [{ translateX: knob.x }, { translateY: knob.y }],
        }]}>
          <MaterialCommunityIcons name="robot-outline" size={26} color={knob.x || knob.y ? '#fff' : p.console} />
        </View>
      </View>
    </View>
  );
}

/** Camera pan / tilt in 15 degree steps; centre button re-centres. */
export function CameraPad({ pan, tilt, onMove, disabled }: {
  pan: number; tilt: number; onMove: (pan: number, tilt: number) => void; disabled?: boolean;
}) {
  const p = usePalette();
  const step = 15;
  const clampP = (v: number) => Math.max(-90, Math.min(90, v));
  const clampT = (v: number) => Math.max(-45, Math.min(60, v));
  const K = (icon: IconName, label: string, f: () => void) => (
    <PadKey icon={icon} label={label} size={44} disabled={disabled} onIn={() => { tick(); f(); }} />
  );
  return (
    <View style={{ alignItems: 'center', gap: 6 }}>
      {K('chevron-up', 'Camera up', () => onMove(pan, clampT(tilt + step)))}
      <View style={{ flexDirection: 'row', gap: 6 }}>
        {K('chevron-left', 'Camera left', () => onMove(clampP(pan + step), tilt))}
        {K('image-filter-center-focus', 'Centre camera', () => onMove(0, 0))}
        {K('chevron-right', 'Camera right', () => onMove(clampP(pan - step), tilt))}
      </View>
      {K('chevron-down', 'Camera down', () => onMove(pan, clampT(tilt - step)))}
      <Text style={{ fontFamily: fonts.numeric, color: p.consoleSoft, fontSize: 12, marginTop: 2 }}>
        pan {Math.round(pan)}°  tilt {Math.round(tilt)}°
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pad: { gap: 8, alignItems: 'center' },
  padRow: { flexDirection: 'row', gap: 8 },
  key: { alignItems: 'center', justifyContent: 'center', borderWidth: 1 },
  stickBase: { borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  stickArrow: { position: 'absolute', alignSelf: 'center' },
  stickRing: { position: 'absolute', borderWidth: 1, borderStyle: 'dashed' },
  knob: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 6 },
});
