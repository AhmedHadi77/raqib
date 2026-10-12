// Live floor plan in blueprint style: rooms tagged by their latest inspection, the robot with its
// field-of-view cone (the same V as the logo) and its recent trail.
import React, { useEffect, useRef, useState } from 'react';
import { Animated, Easing, LayoutChangeEvent, View } from 'react-native';
import Svg, { Circle, G, Line, Path, Polyline, Rect, Text as SvgText } from 'react-native-svg';

import { usePalette } from '@/hooks';
import { fonts, Level, ZONE_SHORT } from '@/theme';

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export interface MapData {
  zones: Record<string, { x: number; y: number; radius?: number }>;
  map: { bounds?: number[] | null; obstacles?: number[][] };
  status: Record<string, { level: Level; issues: number }>;
}

export default function FloorMap({ data, pose, trail, onZonePress, height: maxHeight = 230, selected, live = true }: {
  data: MapData | null;
  pose?: { x: number; y: number; heading_deg: number; zone?: string | null } | null;
  trail?: { x: number | null; y: number | null }[];
  onZonePress?: (zone: string) => void;
  height?: number;
  selected?: string | null;
  live?: boolean;
}) {
  const p = usePalette();
  let height = maxHeight;
  const [w, setW] = useState(0);
  const onLayout = (e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width);
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!live) return;
    const loop = Animated.loop(Animated.timing(pulse, { toValue: 1, duration: 1800, easing: Easing.out(Easing.quad), useNativeDriver: false }));
    loop.start();
    return () => loop.stop();
  }, [live, pulse]);

  const zones = data?.zones ?? {};
  const names = Object.keys(zones);
  let b = data?.map?.bounds as number[] | undefined;
  if (!b || b.length !== 4) {
    const xs = names.map((n) => zones[n].x);
    const ys = names.map((n) => zones[n].y);
    b = xs.length ? [Math.min(...xs) - 1.5, Math.min(...ys) - 1.5, Math.max(...xs) + 1.5, Math.max(...ys) + 1.5] : [-1, -2, 11, 2];
  }
  let [x0, y0, x1, y1] = b;
  if (names.length && (x1 - x0) / (y1 - y0) > 2.2) {
    const ys = names.map((n) => zones[n].y);
    const mid = (Math.min(...ys) + Math.max(...ys)) / 2;
    const half = Math.max((Math.max(...ys) - Math.min(...ys)) / 2 + 2.2, (x1 - x0) / 2.2 / 2);
    y0 = Math.max(y0, mid - half);
    y1 = Math.min(y1, mid + half);
  }
  const pad = 14;
  const s = w ? Math.min((w - pad * 2) / (x1 - x0), (height - pad * 2 - 18) / (y1 - y0)) : 1;
  height = w ? Math.min(height, Math.round((y1 - y0) * s + pad * 2 + 26)) : height;
  const ox = (w - (x1 - x0) * s) / 2;
  const oy = (height - (y1 - y0) * s) / 2 - 4;
  const X = (x: number) => ox + (x - x0) * s;
  const Y = (y: number) => oy + (y1 - y) * s;

  const grid: React.ReactNode[] = [];
  if (w) {
    for (let gx = Math.ceil(x0); gx <= x1; gx++)
      grid.push(<Line key={`gx${gx}`} x1={X(gx)} x2={X(gx)} y1={Y(y1)} y2={Y(y0)} stroke={p.consoleLine} strokeWidth={gx % 5 === 0 ? 1 : 0.5} opacity={0.8} />);
    for (let gy = Math.ceil(y0); gy <= y1; gy++)
      grid.push(<Line key={`gy${gy}`} x1={X(x0)} x2={X(x1)} y1={Y(gy)} y2={Y(gy)} stroke={p.consoleLine} strokeWidth={gy % 5 === 0 ? 1 : 0.5} opacity={0.8} />);
  }
  const pts = (trail ?? []).filter((t) => t.x != null && t.y != null).map((t) => `${X(t.x!)},${Y(t.y!)}`).join(' ');
  const statusColor = (l?: Level) => (l === 'alert' ? '#FF6B6B' : l === 'warn' ? '#FFB224' : l === 'ok' ? '#3DD598' : p.consoleSoft);

  let robot: React.ReactNode = null;
  if (pose && w) {
    const h = (pose.heading_deg * Math.PI) / 180;
    const cx = X(pose.x);
    const cy = Y(pose.y);
    const reach = Math.max(34, 1.3 * s);
    const spread = 0.5;
    const a = [cx + Math.cos(h + spread) * reach, cy - Math.sin(h + spread) * reach];
    const c = [cx + Math.cos(h - spread) * reach, cy - Math.sin(h - spread) * reach];
    const r = 7;
    robot = (
      <G>
        <Path d={`M${cx},${cy} L${a[0]},${a[1]} A${reach},${reach} 0 0 1 ${c[0]},${c[1]} Z`} fill="#1FC8E3" opacity={0.16} />
        {live ? (
          <AnimatedCircle cx={cx} cy={cy} fill="#1FC8E3"
            r={pulse.interpolate({ inputRange: [0, 1], outputRange: [r, r * 3.2] }) as any}
            opacity={pulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 0] }) as any} />
        ) : null}
        <Circle cx={cx} cy={cy} r={r + 2.5} fill={p.console} />
        <Circle cx={cx} cy={cy} r={r} fill="#1FC8E3" />
        <Circle cx={cx + Math.cos(h) * 3} cy={cy - Math.sin(h) * 3} r={2.4} fill={p.console} />
      </G>
    );
  }

  return (
    <View onLayout={onLayout} style={{ height, width: '100%' }}>
      {w ? (
        <Svg width={w} height={height}>
          {grid}
          <Rect x={X(x0)} y={Y(y1)} width={(x1 - x0) * s} height={(y1 - y0) * s} fill="none" stroke={p.consoleSoft} strokeWidth={1.5} opacity={0.55} rx={4} />
          {(data?.map?.obstacles ?? []).map((o, i) => (
            <Rect key={`o${i}`} x={X(o[0])} y={Y(o[3])} width={(o[2] - o[0]) * s} height={(o[3] - o[1]) * s} rx={2}
              fill={p.consoleSoft} opacity={0.35} />
          ))}
          {pts ? <Polyline points={pts} fill="none" stroke="#1FC8E3" strokeWidth={1.6} strokeDasharray="3 4" opacity={0.6} /> : null}
          {names.map((n) => {
            const z = zones[n];
            const st = data?.status?.[n];
            const col = statusColor(st?.level as Level | undefined);
            const half = Math.max(16, (z.radius ?? 1) * s * 0.62);
            const isHome = n.toLowerCase() === 'home';
            const sel = selected === n;
            const cx = X(z.x);
            const cy = Y(z.y);
            return (
              <G key={n} onPress={onZonePress ? () => onZonePress(n) : undefined}>
                {isHome ? (
                  <G>
                    <Rect x={cx - 11} y={cy - 7} width={22} height={14} rx={3} fill="none" stroke={p.consoleSoft} strokeWidth={1.4} />
                    <Line x1={cx - 5} x2={cx + 5} y1={cy} y2={cy} stroke={p.consoleSoft} strokeWidth={1.4} />
                  </G>
                ) : (
                  <Rect x={cx - half} y={cy - half} width={half * 2} height={half * 2} rx={6}
                    fill={col} fillOpacity={st ? 0.14 : 0.04} stroke={col} strokeWidth={sel ? 2.6 : 1.5}
                    strokeDasharray={st ? undefined : '4 3'} />
                )}
                <SvgText x={cx} y={cy + (isHome ? 26 : half + 15)} fontSize={11.5} fontFamily={fonts.bodyStrong}
                  fill={isHome ? p.consoleSoft : p.consoleInk} textAnchor="middle">
                  {isHome ? 'Dock' : ZONE_SHORT(n)}
                </SvgText>
                {st && st.issues && !isHome ? (
                  <G>
                    <Circle cx={cx + half} cy={cy - half} r={9} fill={col} />
                    <SvgText x={cx + half} y={cy - half + 4} fontSize={11} fontFamily={fonts.bodyStrong} fill={p.console} textAnchor="middle">
                      {st.issues}
                    </SvgText>
                  </G>
                ) : null}
              </G>
            );
          })}
          {robot}
          <Line x1={X(x1) - 10 - s} y1={Y(y0) + 12} x2={X(x1) - 10} y2={Y(y0) + 12} stroke={p.consoleSoft} strokeWidth={2} />
          <SvgText x={X(x1) - 10 - s / 2} y={Y(y0) + 24} fontSize={10} fontFamily={fonts.body} fill={p.consoleSoft} textAnchor="middle">1 m</SvgText>
        </Svg>
      ) : null}
    </View>
  );
}
