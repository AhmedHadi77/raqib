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

export async function phoneAddress(): Promise<string | null> {
  if (Platform.OS === 'web') return null;
  try {
    const ip = await Network.getIpAddressAsync();
    return /^\d+\.\d+\.\d+\.\d+$/.test(ip) && ip !== '0.0.0.0' ? ip : null;
  } catch {
    return null;
  }
}

export async function findServer(opts: {
  known?: string[];
  port?: number;
  onProgress?: (checked: number, total: number) => void;
  cancelled?: () => boolean;
} = {}): Promise<FoundServer | null> {
  const port = opts.port ?? 8000;
  const known = Array.from(new Set([...(opts.known ?? []).filter(Boolean), `http://raqib.local:${port}`]));
  const quick = (await Promise.all(known.map((u) => probe(u.replace(/\/+$/, ''), 1500)))).filter(Boolean) as FoundServer[];
  if (quick.length) return quick.sort((a, b) => b.online - a.online)[0];

  const ip = await phoneAddress();
  if (!ip) return null;
  const parts = ip.split('.');
  const prefix = parts.slice(0, 3).join('.');
  const own = Number(parts[3]);
  const hosts: number[] = [];
  for (let i = 1; i <= 254; i++) if (i !== own) hosts.push(i);

  let next = 0;
  let checked = 0;
  const found: FoundServer[] = [];
  const worker = async () => {
    while (next < hosts.length && !found.length && !opts.cancelled?.()) {
      const h = hosts[next++];
      const f = await probe(`http://${prefix}.${h}:${port}`, 1300);
      checked++;
      opts.onProgress?.(checked, hosts.length);
      if (f) found.push(f);
    }
  };
  await Promise.all(Array.from({ length: 32 }, worker));
  return found.sort((a, b) => b.online - a.online)[0] ?? null;
}
