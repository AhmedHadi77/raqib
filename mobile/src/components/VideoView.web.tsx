// Web version: the browser's built-in WebRTC, falling back to JPEG snapshots.
import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { api, authUrl } from '@/services/api';
import { useAppSelector } from '@/store';
import { fonts } from '@/theme';

export default function VideoView() {
  const robotId = useAppSelector((s) => s.session.robotId);
  const online = useAppSelector((s) => s.robot.online);
  const sim = useAppSelector((s) => s.robot.simulation);
  const webots = useAppSelector((s) => s.robot.info?.simulator === 'webots');
  const privacy = useAppSelector((s) => s.robot.telemetry?.privacy_mode);
  const ref = useRef<HTMLVideoElement | null>(null);
  const rtcOnRobot = useAppSelector((s) => (s.robot.info as any)?.webrtc) !== false;
  const [err, setErr] = useState<string | null>(rtcOnRobot ? null : 'no webrtc');
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);

  // no picture within 8 s (e.g. WebRTC not installed on the robot) -> fall back to snapshots
  useEffect(() => {
    if (!online || privacy || playing || err) return;
    const t = setTimeout(() => setErr('timeout'), 8000);
    return () => clearTimeout(t);
  }, [online, privacy, playing, err]);

  useEffect(() => {
    if (!err || !online) return;
    const t = setInterval(() => setFrame((n) => n + 1), 500);
    return () => clearInterval(t);
  }, [err, online]);

  useEffect(() => {
    if (!rtcOnRobot) setErr('no webrtc');
  }, [rtcOnRobot]);

  useEffect(() => {
    if (!online || privacy || !rtcOnRobot) return;
    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.ontrack = (e) => {
      if (ref.current) ref.current.srcObject = e.streams[0];
    };
    (async () => {
      try {
        await pc.setLocalDescription(await pc.createOffer());
        await new Promise<void>((r) => {
          if (pc.iceGatheringState === 'complete') return r();
          const t = setTimeout(r, 3000);
          pc.onicegatheringstatechange = () => pc.iceGatheringState === 'complete' && (clearTimeout(t), r());
        });
        const ans = await api.webrtcOffer(pc.localDescription!.sdp, 'offer', robotId);
        await pc.setRemoteDescription(ans as RTCSessionDescriptionInit);
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      }
    })();
    return () => pc.close();
  }, [online, robotId, privacy, rtcOnRobot]);

  return (
    <View style={styles.box}>
      {!online ? (
        <Text style={styles.center}>Robot offline</Text>
      ) : privacy ? (
        <Text style={styles.center}>Privacy mode is on - the camera is off</Text>
      ) : err ? (
        <img src={authUrl(`/robots/${robotId}/frame.jpg?n=${frame}`)} alt="Robot camera"
          style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        <>
          <video ref={ref} autoPlay playsInline muted onPlaying={() => setPlaying(true)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          {!playing ? <Text style={[styles.center, StyleSheet.absoluteFill]}>Connecting video…</Text> : null}
        </>
      )}
      <View style={styles.badges}>
        <Text style={styles.badge}>{err ? 'Snapshots' : playing ? 'Live' : 'Connecting'}</Text>
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
