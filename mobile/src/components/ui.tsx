// Raqib UI kit shared by every screen.
import { MaterialCommunityIcons } from '@expo/vector-icons';
import React from 'react';
import {
  Pressable, RefreshControl, ScrollView, StyleProp, StyleSheet, Text, TextStyle, View, ViewStyle,
} from 'react-native';
import { Modal, Portal } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Defs, LinearGradient, Mask, Path, Rect, Stop } from 'react-native-svg';

import { usePalette } from '@/hooks';
import { BRAND, fonts, Level, levelColors } from '@/theme';

export type IconName = keyof typeof MaterialCommunityIcons.glyphMap;

// ------------------------------------------------------------------ brand
/** The Raqib mark: an R whose bowl is the robot's watching eye. */
export function Logo({ size = 40, tile = true, mono }: { size?: number; tile?: boolean; mono?: string }) {
  const id = React.useId().replace(/:/g, '');
  return (
    <Svg width={size} height={size} viewBox="0 0 100 100">
      <Defs>
        <LinearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor="#4F7BFF" />
          <Stop offset="1" stopColor="#1FD1E8" />
        </LinearGradient>
        <Mask id={`m${id}`}>
          <Rect x="0" y="0" width="100" height="100" fill="#fff" />
          <Circle cx="49" cy="41" r="2.9" fill="#000" />
        </Mask>
      </Defs>
      {tile ? <Rect width="100" height="100" rx="24" fill={BRAND.navy} /> : null}
      <Path d="M30 75 L30 25 L52 25 A16 16 0 0 1 52 57 L30 57 M50 57 L70 75" fill="none" stroke={mono ?? `url(#g${id})`} strokeWidth={11.5}
        strokeLinecap="round" strokeLinejoin="round" />
      {tile ? (
        <>
          <Circle cx="49" cy="41" r="6.6" fill="#fff" />
          <Circle cx="49" cy="41" r="2.9" fill={BRAND.navy} />
        </>
      ) : (
        <Circle cx="49" cy="41" r="6.6" fill={mono ?? '#fff'} mask={`url(#m${id})`} />
      )}
    </Svg>
  );
}

export function Wordmark({ size = 22, color }: { size?: number; color?: string }) {
  const p = usePalette();
  return (
    <Text style={{ fontFamily: fonts.display, fontSize: size, letterSpacing: -0.04 * size, color: color ?? p.ink, lineHeight: size * 1.1 }}>
      raqib
    </Text>
  );
}

// ------------------------------------------------------------------ layout
export function Screen({ children, scroll = true, padded = true, onRefresh, refreshing = false, bottom = 130 }: {
  children: React.ReactNode; scroll?: boolean; padded?: boolean; onRefresh?: () => void; refreshing?: boolean; bottom?: number;
}) {
  const p = usePalette();
  const inner = <View style={[styles.inner, padded && styles.padded]}>{children}</View>;
  return scroll ? (
    <ScrollView style={{ flex: 1, backgroundColor: p.paper }} contentContainerStyle={{ paddingBottom: bottom }}
      keyboardShouldPersistTaps="handled"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={p.primary} /> : undefined}>
      {inner}
    </ScrollView>
  ) : (
    <View style={{ flex: 1, backgroundColor: p.paper }}>{inner}</View>
  );
}

export function H1({ children, style }: { children: React.ReactNode; style?: StyleProp<TextStyle> }) {
  const p = usePalette();
  return <Text style={[{ fontFamily: fonts.display, fontSize: 28, lineHeight: 32, color: p.ink, letterSpacing: -0.6 }, style]}>{children}</Text>;
}

export function H2({ children, style }: { children: React.ReactNode; style?: StyleProp<TextStyle> }) {
  const p = usePalette();
  return <Text style={[{ fontFamily: fonts.heading, fontSize: 17, lineHeight: 22, color: p.ink, letterSpacing: -0.2 }, style]}>{children}</Text>;
}

export function Body({ children, soft, small, style, numberOfLines, strong }: {
  children: React.ReactNode; soft?: boolean; small?: boolean; style?: StyleProp<TextStyle>; numberOfLines?: number; strong?: boolean;
}) {
  const p = usePalette();
  return (
    <Text numberOfLines={numberOfLines}
      style={[{
        fontFamily: strong ? fonts.bodyStrong : fonts.body, fontSize: small ? 13 : 15, lineHeight: small ? 18 : 22,
        color: soft ? p.inkSoft : p.ink,
      }, style]}>
      {children}
    </Text>
  );
}

export function Section({ title, action, children, style, note }: {
  title: string; action?: React.ReactNode; children: React.ReactNode; style?: StyleProp<ViewStyle>; note?: string;
}) {
  return (
    <View style={[{ marginTop: 26 }, style]}>
      <View style={styles.sectionHead}>
        <View style={{ flex: 1 }}>
          <H2>{title}</H2>
          {note ? <Body small soft style={{ marginTop: 2 }}>{note}</Body> : null}
        </View>
        {action}
      </View>
      {children}
    </View>
  );
}

export function Card({ children, style, onPress, radius = 16, tone = 'surface' }: {
  children: React.ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; radius?: number; tone?: 'surface' | 'sunken' | 'console';
}) {
  const p = usePalette();
  const bg = tone === 'console' ? p.console : tone === 'sunken' ? p.sunken : p.surface;
  const border = tone === 'console' ? p.consoleLine : p.line;
  const base: StyleProp<ViewStyle> = [{ backgroundColor: bg, borderRadius: radius, borderWidth: StyleSheet.hairlineWidth, borderColor: border, padding: 14 }, style];
  if (!onPress) return <View style={base}>{children}</View>;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [base, pressed && { opacity: 0.86 }]}>
      {children}
    </Pressable>
  );
}

export function Divider({ inset = 0 }: { inset?: number }) {
  const p = usePalette();
  return <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: p.line, marginLeft: inset }} />;
}

// ------------------------------------------------------------------ status
export function Pill({ level = 'idle', label, icon, solid, small }: { level?: Level; label: string; icon?: IconName; solid?: boolean; small?: boolean }) {
  const p = usePalette();
  const c = levelColors(p, level);
  return (
    <View style={[styles.pill, small && { paddingHorizontal: 8, paddingVertical: 3 }, { backgroundColor: solid ? c.fg : c.bg }]}>
      {icon ? <MaterialCommunityIcons name={icon} size={small ? 12 : 14} color={solid ? p.surface : c.fg} /> : <View style={[styles.dot, { backgroundColor: solid ? p.surface : c.fg }]} />}
      <Text style={{ fontFamily: fonts.bodyStrong, fontSize: small ? 11.5 : 12.5, color: solid ? p.surface : c.fg }}>{label}</Text>
    </View>
  );
}

export function Sparkline({ values, color, width = 120, height = 32 }: { values: (number | null | undefined)[]; color: string; width?: number; height?: number }) {
  const v = values.filter((x): x is number => typeof x === 'number');
  if (v.length < 2) return <View style={{ width, height }} />;
  const min = Math.min(...v);
  const max = Math.max(...v);
  const span = max - min || 1;
  const step = width / (v.length - 1);
  const d = v.map((y, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(height - 3 - ((y - min) / span) * (height - 6)).toFixed(1)}`).join(' ');
  return (
    <Svg width={width} height={height}>
      <Path d={d} stroke={color} strokeWidth={2} fill="none" strokeLinejoin="round" strokeLinecap="round" />
    </Svg>
  );
}

/** A live reading: label, big number, verdict, tiny trend. */
export function Metric({ label, value, unit, note, level = 'idle', trend, icon }: {
  label: string; value: string | number | null | undefined; unit?: string; note?: string; level?: Level;
  trend?: (number | null | undefined)[]; icon: IconName;
}) {
  const p = usePalette();
  const c = levelColors(p, level);
  return (
    <View style={[styles.metric, { backgroundColor: p.surface, borderColor: p.line }]}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <MaterialCommunityIcons name={icon} size={16} color={p.inkSoft} />
        <Body small soft style={{ flex: 1 }}>{label}</Body>
      </View>
      <View style={styles.metricRow}>
        <Text style={{ fontFamily: fonts.numeric, fontSize: 30, color: p.ink, letterSpacing: -0.8 }}>{value ?? '—'}</Text>
        {value != null && unit ? <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 14, color: p.inkSoft, marginLeft: 3, marginBottom: 5 }}>{unit}</Text> : null}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        {level !== 'idle' ? <View style={[styles.dot, { backgroundColor: c.fg }]} /> : null}
        <Body small numberOfLines={1} style={{ color: level === 'idle' ? p.inkSoft : c.fg, fontFamily: fonts.bodyMedium, flex: 1 }}>
          {note ?? ' '}
        </Body>
      </View>
      {trend ? <View style={{ marginTop: 6 }}><Sparkline values={trend} color={level === 'idle' ? p.primary : c.fg} width={130} height={24} /></View> : null}
    </View>
  );
}

export function ListRow({ icon, title, detail, right, onPress, danger, tint }: {
  icon: IconName; title: string; detail?: string; right?: React.ReactNode; onPress?: () => void; danger?: boolean; tint?: string;
}) {
  const p = usePalette();
  const color = danger ? p.danger : tint ?? p.primary;
  const body = (
    <View style={styles.row}>
      <View style={[styles.rowIcon, { backgroundColor: danger ? p.dangerSoft : p.primarySoft }]}>
        <MaterialCommunityIcons name={icon} size={19} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 15, color: danger ? p.danger : p.ink }}>{title}</Text>
        {detail ? <Body small soft>{detail}</Body> : null}
      </View>
      {right ?? (onPress ? <MaterialCommunityIcons name="chevron-right" size={20} color={p.inkFaint} /> : null)}
    </View>
  );
  return onPress ? (
    <Pressable onPress={onPress} style={({ pressed }) => pressed && { opacity: 0.6 }} accessibilityRole="button">{body}</Pressable>
  ) : body;
}

export function IconBtn({ icon, onPress, label, color, bg, size = 40, disabled }: {
  icon: IconName; onPress?: () => void; label: string; color?: string; bg?: string; size?: number; disabled?: boolean;
}) {
  const p = usePalette();
  return (
    <Pressable onPress={onPress} disabled={disabled} accessibilityLabel={label} accessibilityRole="button" hitSlop={6}
      style={({ pressed }) => [{
        width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center',
        backgroundColor: bg ?? p.surface, borderWidth: bg ? 0 : StyleSheet.hairlineWidth, borderColor: p.line,
        opacity: disabled ? 0.4 : pressed ? 0.7 : 1,
      }]}>
      <MaterialCommunityIcons name={icon} size={size * 0.5} color={color ?? p.ink} />
    </Pressable>
  );
}

/** Pill-shaped segmented control. */
export function Segmented<T extends string>({ value, options, onChange, dark }: {
  value: T; options: { value: T; label: string; icon?: IconName }[]; onChange: (v: T) => void; dark?: boolean;
}) {
  const p = usePalette();
  const track = dark ? p.console2 : p.sunken;
  return (
    <View style={[styles.seg, { backgroundColor: track }]}>
      {options.map((o) => {
        const on = o.value === value;
        const fg = on ? (dark ? p.console : p.ink) : dark ? p.consoleSoft : p.inkSoft;
        return (
          <Pressable key={o.value} onPress={() => onChange(o.value)} accessibilityRole="button" accessibilityState={{ selected: on }}
            style={[styles.segBtn, on && { backgroundColor: dark ? p.consoleInk : p.surface }]}>
            {o.icon ? <MaterialCommunityIcons name={o.icon} size={15} color={fg} /> : null}
            <Text style={{ fontFamily: fonts.bodyStrong, fontSize: 13, color: fg }}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Chip({ label, onPress, icon, active }: { label: string; onPress?: () => void; icon?: IconName; active?: boolean }) {
  const p = usePalette();
  return (
    <Pressable onPress={onPress} accessibilityRole="button"
      style={({ pressed }) => [styles.chip, {
        backgroundColor: active ? p.ink : pressed ? p.primarySoft : p.surface, borderColor: active ? p.ink : p.line,
      }]}>
      {icon ? <MaterialCommunityIcons name={icon} size={15} color={active ? p.paper : p.primary} /> : null}
      <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 13.5, color: active ? p.paper : p.ink }}>{label}</Text>
    </Pressable>
  );
}

export function EmptyState({ icon, title, body, action }: { icon: IconName; title: string; body: string; action?: React.ReactNode }) {
  const p = usePalette();
  return (
    <View style={{ alignItems: 'center', paddingVertical: 44, paddingHorizontal: 24, gap: 8 }}>
      <View style={{ width: 60, height: 60, borderRadius: 18, backgroundColor: p.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
        <MaterialCommunityIcons name={icon} size={28} color={p.primary} />
      </View>
      <H2 style={{ marginTop: 8, textAlign: 'center' }}>{title}</H2>
      <Body soft style={{ textAlign: 'center', maxWidth: 320 }}>{body}</Body>
      {action}
    </View>
  );
}

/** Bottom sheet built on Paper's Modal. */
export function Sheet({ visible, onDismiss, children, title }: { visible: boolean; onDismiss: () => void; children: React.ReactNode; title?: string }) {
  const p = usePalette();
  const insets = useSafeAreaInsets();
  return (
    <Portal>
      <Modal visible={visible} onDismiss={onDismiss}
        style={{ justifyContent: 'flex-end', margin: 0 }}
        contentContainerStyle={[styles.sheet, { backgroundColor: p.surface, paddingBottom: 18 + insets.bottom }]}>
        <View style={[styles.grabber, { backgroundColor: p.line }]} />
        {title ? <H2 style={{ fontSize: 20, marginBottom: 6 }}>{title}</H2> : null}
        {children}
      </Modal>
    </Portal>
  );
}

const styles = StyleSheet.create({
  inner: { width: '100%', maxWidth: 860, alignSelf: 'center' },
  padded: { paddingHorizontal: 16, paddingTop: 8 },
  sectionHead: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 10, gap: 10 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, alignSelf: 'flex-start' },
  dot: { width: 7, height: 7, borderRadius: 4 },
  metric: { flexGrow: 1, flexBasis: '46%', borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, padding: 12, gap: 2 },
  metricRow: { flexDirection: 'row', alignItems: 'flex-end', marginTop: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12 },
  rowIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  seg: { flexDirection: 'row', borderRadius: 999, padding: 3, gap: 2 },
  segBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 999 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: StyleSheet.hairlineWidth, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 8 },
  sheet: { marginTop: 'auto', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingTop: 10, width: '100%', maxWidth: 640, alignSelf: 'center' },
  grabber: { width: 40, height: 4, borderRadius: 2, alignSelf: 'center', marginBottom: 14 },
});
