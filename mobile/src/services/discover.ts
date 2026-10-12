// Find the Raqib server on the phone's Wi-Fi without typing an IP address.
// 1) try the addresses we already know, 2) scan every address of the phone's own network (x.x.x.1-254)
// for the server's /health page. Takes 2-10 s on a normal home or campus network.
import * as Network from 'expo-network';
import { Platform } from 'react-native';

export type FoundServer = { url: string; site?: string; robots: number; online: number };

async function probe(url: string, ms: number): Promise<FoundServer | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(`${url}/health`, { signal: ctrl.signal, headers: { Accept: 'application/json' } });
    if (!r.ok) return null;
    const j: any = await r.json();
    if (j?.service !== 'raqib' && !(j?.status === 'ok' && 'mqtt_connected' in (j ?? {}))) return null;
    const robots = Object.values(j.robots ?? {}) as any[];
    return { url, site: j.site, robots: robots.length, online: robots.filter((x) => x?.online).length };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

const PRIVATE = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/;

export async function phoneAddress(): Promise<string | null> {
  if (Platform.OS === 'web') return null;
  try {
    const ip = await Network.getIpAddressAsync();
    return /^\d+\.\d+\.\d+\.\d+$/.test(ip) && ip !== '0.0.0.0' ? ip : null;
  } catch {
    return null;
  }
}

/** Every local network address of the phone, including its own hotspot (Wi-Fi info alone reports 0.0.0.0
 *  while the phone is sharing its connection). Uses the WebRTC engine's list of host addresses. */
async function allPhoneAddresses(): Promise<string[]> {
  const out = new Set<string>();
  const wifi = await phoneAddress();
  if (wifi) out.add(wifi);
  let RTC: any = null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    RTC = require('react-native-webrtc');
  } catch {
    RTC = null;
  }
  if (RTC?.RTCPeerConnection) {
    let pc: any = null;
    try {
      pc = new RTC.RTCPeerConnection({ iceServers: [] });
      const grab = (text: string) => {
        for (const m of text.matchAll(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) \d+ typ host/g)) out.add(m[1]);
      };
      pc.addEventListener('icecandidate', (e: any) => e?.candidate?.candidate && grab(e.candidate.candidate));
      pc.createDataChannel('find');
      await pc.setLocalDescription(await pc.createOffer({}));
      await new Promise((r) => setTimeout(r, 1500));
      grab(pc.localDescription?.sdp ?? '');
    } catch {
      /* no WebRTC: Wi-Fi address only */
    } finally {
      try { pc?.close(); } catch { /* closed */ }
    }
  }
  return [...out].filter((ip) => PRIVATE.test(ip));
}

export async function findServer(opts: {
  known?: string[];
  port?: number;
  onProgress?: (checked: number, total: number) => void;
  cancelled?: () => boolean;
} = {}): Promise<FoundServer | null> {
  const port = opts.port ?? 8000;
  // the robot's own Wi-Fi (Raqib-Robot) always gives the robot 10.42.0.1; Pi hostnames for networks with mDNS
  const known = Array.from(new Set([...(opts.known ?? []).filter(Boolean), `http://10.42.0.1:${port}`,
    `http://robot01.local:${port}`, `http://raqib.local:${port}`]));
  const quick = (await Promise.all(known.map((u) => probe(u.replace(/\/+$/, ''), 1500)))).filter(Boolean) as FoundServer[];
  if (quick.length) return quick.sort((a, b) => b.online - a.online)[0];

  const ips = await allPhoneAddresses();
  if (!ips.length) return null;
  const hosts: string[] = [];
  for (const ip of ips) {
    const parts = ip.split('.');
    const prefix = parts.slice(0, 3).join('.');
    for (let i = 1; i <= 254; i++) {
      const h = `${prefix}.${i}`;
      if (h !== ip && !hosts.includes(h)) hosts.push(h);
    }
  }

  let next = 0;
  let checked = 0;
  const found: FoundServer[] = [];
  const worker = async () => {
    while (next < hosts.length && !found.length && !opts.cancelled?.()) {
      const h = hosts[next++];
      const f = await probe(`http://${h}:${port}`, 1300);
      checked++;
      opts.onProgress?.(checked, hosts.length);
      if (f) found.push(f);
    }
  };
  await Promise.all(Array.from({ length: 32 }, worker));
  return found.sort((a, b) => b.online - a.online)[0] ?? null;
}
