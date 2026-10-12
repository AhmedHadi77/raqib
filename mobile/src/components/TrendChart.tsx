// Line chart with comfort band, min/max/latest labels and a time axis (react-native-svg, no extra deps).
import React, { useState } from 'react';
import { LayoutChangeEvent, Text, View } from 'react-native';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { usePalette } from '@/hooks';
import { fonts } from '@/theme';

export interface TrendPoint {
  ts: number;
  v: number | null | undefined;
}

export default function TrendChart({
  title, unit, points, color, band, decimals = 1, height = 130,
}: {
  title: string;
  unit: string;
  points: TrendPoint[];
  color: string;
  band?: [number, number]; // shaded "good" range
  decimals?: number;
  height?: number;
}) {
  const p = usePalette();
  const [w, setW] = useState(300);
  const data = points.filter((x): x is { ts: number; v: number } => typeof x.v === 'number');
  const latest = data.length ? data[data.length - 1].v : null;
  const padL = 4;
  const padR = 4;
  const padT = 8;
  const padB = 18;
  const vals = data.map((d) => d.v).concat(band ?? []);
  const min = vals.length ? Math.min(...vals) : 0;
  const max = vals.length ? Math.max(...vals) : 1;
  const span = max - min || 1;
  const lo = min - span * 0.08;
  const hi = max + span * 0.08;
  const t0 = data.length ? data[0].ts : 0;
  const t1 = data.length ? data[data.length - 1].ts : 1;
  const x = (ts: number) => padL + ((ts - t0) / (t1 - t0 || 1)) * (w - padL - padR);
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (height - padT - padB);
  const path = data.map((d, i) => `${i ? 'L' : 'M'}${x(d.ts).toFixed(1)},${y(d.v).toFixed(1)}`).join(' ');
  const fmt = (v: number) => v.toFixed(decimals);
  const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <View onLayout={(e: LayoutChangeEvent) => setW(Math.max(160, e.nativeEvent.layout.width))}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 4 }}>
        <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 13.5, color: p.inkSoft }}>{title}</Text>
        <Text style={{ fontFamily: fonts.numeric, fontSize: 22, color: p.ink }}>
          {latest != null ? fmt(latest) : '—'}
          <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 13, color: p.inkSoft }}> {unit}</Text>
        </Text>
      </View>
      <Svg width={w} height={height}>
        {band ? (
          <Rect x={padL} width={w - padL - padR} y={y(band[1])} height={Math.max(0, y(band[0]) - y(band[1]))}
            fill={p.ok} opacity={0.07} />
        ) : null}
        <Line x1={padL} x2={w - padR} y1={height - padB} y2={height - padB} stroke={p.line} strokeWidth={1} />
        {data.length > 1 ? <Path d={path} stroke={color} strokeWidth={2.2} fill="none" strokeLinejoin="round" /> : null}
        {data.length ? <Circle cx={x(t1)} cy={y(latest as number)} r={3.5} fill={color} /> : null}
      </Svg>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: -14 }}>
        <Text style={{ fontFamily: fonts.body, fontSize: 11, color: p.inkSoft }}>{data.length ? time(t0) : ''}</Text>
        <Text style={{ fontFamily: fonts.body, fontSize: 11, color: p.inkSoft }}>
          {data.length ? `min ${fmt(Math.min(...data.map((d) => d.v)))} · max ${fmt(Math.max(...data.map((d) => d.v)))}` : 'Waiting for data…'}
        </Text>
        <Text style={{ fontFamily: fonts.body, fontSize: 11, color: p.inkSoft }}>{data.length ? time(t1) : ''}</Text>
      </View>
    </View>
  );
}
