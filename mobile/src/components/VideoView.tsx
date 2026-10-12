// Live camera.  Native dev build / APK: WebRTC (react-native-webrtc, robot answers with aiortc).
// Expo Go (no native WebRTC module) or robot without WebRTC: refreshing JPEG snapshots.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { api, authUrl } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts } from '@/theme';

let RTC: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  RTC = require('react-native-webrtc');
  if (!RTC?.RTCPeerConnection) RTC = null;
} catch {
  RTC = null;
}

function waitIce(pc: any, ms = 3000) {
  return new Promise<void>((resolve) => {
    if (pc.iceGatheringState === 'complete') return resolve();
    const t = setTimeout(resolve, ms);
    pc.addEventListener('icegatheringstatechange', () => {
      if (pc.iceGatheringState === 'complete') {
        clearTimeout(t);
        resolve();
      }
    });
  });
}

function WebRTCVideo({ onFail }: { onFail: (e: string) => void }) {
  const robotId = useAppSelector((s) => s.session.robotId);
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let pc: any;
    let alive = true;
    (async () => {
      try {
        pc = new RTC.RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
        pc.addTransceiver('video', { direction: 'recvonly' });
        pc.addEventListener('track', (e: any) => alive && setUrl(e.streams[0].toURL()));
        await pc.setLocalDescription(await pc.createOffer({}));
        await waitIce(pc);
        const ans = await api.webrtcOffer(pc.localDescription.sdp, 'offer', robotId);
        await pc.setRemoteDescription(new RTC.RTCSessionDescription(ans));
      } catch (e: any) {
        onFail(e?.message ?? String(e));
      }
    })();
    return () => {
      alive = false;
      pc?.close();
    };
  }, [robotId, onFail]);
  useEffect(() => {
    if (url) return;
    const t = setTimeout(() => onFail('no video after 10 s'), 10000);
    return () => clearTimeout(t);
  }, [url, onFail]);
  if (!url) return <Text style={styles.center}>Connecting video…</Text>;
  return <RTC.RTCView streamURL={url} style={StyleSheet.absoluteFill} objectFit="cover" />;
}

function FrameVideo() {
  const robotId = useAppSelector((s) => s.session.robotId);
  const [n, setN] = useState(0);
  const [shown, setShown] = useState<string | null>(null);
  const loading = useRef(false);
  useEffect(() => {
    const t = setInterval(() => {
      if (!loading.current) setN((x) => x + 1);
    }, 500);
    return () => clearInterval(t);
  }, []);
  const next = authUrl(`/robots/${robotId}/frame.jpg?n=${n}`);
  return (
    <>
      {shown && <Image source={{ uri: shown }} style={StyleSheet.absoluteFill} resizeMode="cover" fadeDuration={0} />}
      <Image key={next} source={{ uri: next }} style={{ width: 1, height: 1, opacity: 0 }}
        onLoadStart={() => (loading.current = true)}
        onLoad={() => { loading.current = false; setShown(next); }}
        onError={() => (loading.current = false)} />
    </>
  );
}

export default function VideoView() {
  const online = useAppSelector((s) => s.robot.online);
  const sim = useAppSelector((s) => s.robot.simulation);
  const webots = useAppSelector((s) => s.robot.info?.simulator === 'webots');
  const privacy = useAppSelector((s) => s.robot.telemetry?.privacy_mode);
  const [rtcFailed, setRtcFailed] = useState<string | null>(null);
  const onFail = useCallback((e: string) => setRtcFailed(e), []);
  const rtcOnRobot = useAppSelector((s) => (s.robot.info as any)?.webrtc) !== false;
  const useRtc = RTC && !rtcFailed && rtcOnRobot;
  return (
    <View style={styles.box}>
      {!online ? (
        <Text style={styles.center}>Robot offline</Text>
      ) : privacy ? (
        <Text style={styles.center}>Privacy mode is on - the camera is off</Text>
      ) : useRtc ? (
        <WebRTCVideo onFail={onFail} />
      ) : (
        <FrameVideo />
      )}
      <View style={styles.badges}>
        <Text style={styles.badge}>{useRtc ? 'Live' : 'Snapshots'}</Text>
        {sim ? <Text style={[styles.badge, { backgroundColor: '#6A3FA0D0' }]}>{webots ? 'Webots' : 'Simulation'}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { width: '100%', aspectRatio: 4 / 3, backgroundColor: '#0B1114', borderRadius: 16, overflow: 'hidden' },
  center: { color: '#B9C6C9', textAlign: 'center', marginTop: '36%', fontFamily: fonts.body },
  badges: { position: 'absolute', top: 10, left: 10, flexDirection: 'row', gap: 6 },
  badge: { color: '#fff', backgroundColor: '#000000A0', paddingHorizontal: 9, paddingVertical: 3, borderRadius: 999, overflow: 'hidden', fontSize: 12, fontFamily: fonts.bodyStrong },
});
