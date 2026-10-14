// Demo robot that lives inside the phone: every screen works with no laptop, no robot and no internet.
// The rooms, sensor values, camera pictures, inspection reports and agent replies were recorded from the
// real software running the simulated robot (tools/make_demo_data.py); this file moves the robot around,
// answers the app's API calls and streams live telemetry like the real server does.
import type {
  AgentStep, ChatResponse, ExamSession, InspectionReport, MonitorStatus, ReportListItem, Schedule,
  ServerMessage, Telemetry, UserAccount, ZoneInspection,
} from '@/types';

import DATA from './demoData.json';
import { DEMO_IMAGES } from './demoImages';

export const DEMO_URL = 'demo://raqib';
export const isDemo = (url?: string | null) => !!url && url.startsWith('demo:');

export class DemoError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const D: any = DATA;
const RID = 'robot01';
const ZONES: Record<string, { x: number; y: number; radius?: number }> = D.robot.info.zones;
const NAMES: Record<string, string> = {
  Home: 'Home', IoT_Lab: 'IoT Lab', LectureHall_B: 'Lecture Hall B', LectureHall_A: 'Lecture Hall A', Exam_Hall: 'Exam Hall',
};
const nice = (z: string | null | undefined) => (z ? NAMES[z] ?? z.replace(/_/g, ' ') : 'the corridor');
const now = () => Date.now() / 1000;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const uid = () => Math.random().toString(16).slice(2, 14);

// ------------------------------------------------------------------ robot state
const R = {
  x: 0, y: 0, h: 0, odo: 0,
  state: 'IDLE' as Telemetry['state'],
  estop: false, privacy: false, pan: 0, tilt: 0,
  battery: 100,
  drive: { l: 0, r: 0, at: 0 },
  busy: 0,                       // >0 while a scripted motion runs
  cancel: 0,                     // bumped by stop / estop
  stopCount: 0,
};
const listeners = new Set<(m: ServerMessage) => void>();
let ticker: ReturnType<typeof setInterval> | null = null;

function emit(m: ServerMessage) {
  listeners.forEach((fn) => { try { fn(m); } catch { /* screen gone */ } });
}

function zoneAt(x = R.x, y = R.y): string | null {
  let best: string | null = null;
  let bestD = 1e9;
  for (const [name, z] of Object.entries(ZONES)) {
    const d = Math.hypot(x - z.x, y - z.y);
    if (d <= (z.radius ?? 1) && d < bestD) { best = name; bestD = d; }
  }
  return best;
}
const near = () => {
  let best = 'Home';
  let bestD = 1e9;
  for (const [name, z] of Object.entries(ZONES)) {
    const d = Math.hypot(R.x - z.x, R.y - z.y);
    if (d < bestD) { best = name; bestD = d; }
  }
  return best;
};
const room = (z = near()) => D.rooms[z] ?? D.rooms.Home;

function telemetry(): Telemetry {
  const base = room().telemetry;
  const t: any = clone(base);
  const z = zoneAt();
  Object.assign(t, {
    v: 1, robot_id: RID, ts: now(), state: R.estop ? 'EMERGENCY_STOP' : R.state, simulation: true, privacy_mode: R.privacy,
    battery: { voltage: +(6.6 + 1.8 * R.battery / 100).toFixed(2), percent: Math.round(R.battery * 10) / 10 },   // 2 x 18650
    pose: { x: +R.x.toFixed(3), y: +R.y.toFixed(3), heading_deg: +(((R.h + 540) % 360) - 180).toFixed(1), zone: z, odometer_m: +R.odo.toFixed(2) },
    motors: { left: R.drive.l, right: R.drive.r },
    pan_tilt: { pan: R.pan, tilt: R.tilt },
    imu: { yaw_deg: +R.h.toFixed(1), pitch_deg: -0.1, roll_deg: -0.3 },
  });
  if (!z) t.environment = D.rooms.Home.telemetry.environment;
  t.safety = { ...(t.safety ?? {}), blocked: false, safe_hold: false, cloud_silent_s: 0.4, stop_count: R.stopCount };
  return t;
}

function info() {
  return { ...clone(D.robot.info), simulation: true, simulator: '2d', webrtc: false, demo: true };
}

function tick() {
  const dt = 0.1;
  if (R.drive.l || R.drive.r) {
    if (Date.now() - R.drive.at > 700 || R.estop) R.drive = { l: 0, r: 0, at: 0 };
    else {
      const v = ((R.drive.l + R.drive.r) / 2) * 0.5;
      const w = ((R.drive.r - R.drive.l) / 0.3) * 0.5 * (180 / Math.PI);
      R.h += w * dt;
      step(v * dt);
    }
  }
  R.battery = Math.max(5, R.battery - 0.0008);
}

function step(d: number) {
  const nx = R.x + Math.cos((R.h * Math.PI) / 180) * d;
  const ny = R.y + Math.sin((R.h * Math.PI) / 180) * d;
  const b = D.map?.map?.bounds as number[] | undefined;
  if (b && (nx < b[0] + 0.2 || nx > b[2] - 0.2 || ny < b[1] + 0.2 || ny > b[3] - 0.2)) return;   // walls
  R.x = nx; R.y = ny; R.odo += Math.abs(d);
}

function startTicker() {
  if (ticker) return;
  let n = 0;
  ticker = setInterval(() => {
    tick();
    if (++n % 5 === 0) emit({ kind: 'telemetry', robot_id: RID, data: telemetry() });
  }, 100);
}

// ------------------------------------------------------------------ scripted motion
async function motion<T>(fn: (token: number) => Promise<T>): Promise<T> {
  if (R.estop) throw new DemoError(409, 'Emergency stop is on. Release it first (Reset).');
  const token = ++R.cancel;
  R.busy++;
  if (R.state === 'IDLE') R.state = 'AUTONOMOUS_PATROL';
  try {
    return await fn(token);
  } finally {
    R.busy--;
    if (!R.busy && !R.estop) R.state = 'IDLE';
  }
}
const alive = (token: number) => token === R.cancel && !R.estop;

async function turnBy(deg: number, token: number) {
  const steps = Math.max(1, Math.round(Math.abs(deg) / 9));
  for (let i = 0; i < steps && alive(token); i++) {
    R.h += deg / steps;
    await sleep(100);
  }
}
async function forward(m: number, token: number) {
  const steps = Math.max(1, Math.round(Math.abs(m) / 0.05));
  for (let i = 0; i < steps && alive(token); i++) {
    step(m / steps);
    await sleep(100);
  }
}
async function goTo(x: number, y: number, token: number) {
  const target = (Math.atan2(y - R.y, x - R.x) * 180) / Math.PI;
  const d = Math.hypot(x - R.x, y - R.y);
  if (d < 0.05) return;
  await turnBy(((target - R.h + 540) % 360) - 180, token);
  await forward(d, token);
}
async function goToZone(z: string, token: number) {
  const p = ZONES[z];
  if (!p) throw new DemoError(400, `unknown room '${z}'`);
  await goTo(p.x, p.y, token);
  await turnBy(((0 - R.h + 540) % 360) - 180, token);
}

// ------------------------------------------------------------------ commands
async function command(action: string, p: any): Promise<any> {
  const ok = (result: any = {}) => ({ v: 1, id: uid(), action, status: 'ok', result, error: null, type: 'ack', ts: now(), robot_id: RID });
  if (['drive', 'move', 'turn', 'go_to_zone', 'go_to_point', 'set_home'].includes(action)) R.pan = 0;   // driving ends a look-around
  switch (action) {
    case 'drive':
      if (R.estop) return { ...ok(), status: 'rejected', error: 'emergency stop is on' };
      R.drive = { l: +p.left || 0, r: +p.right || 0, at: Date.now() };
      R.state = R.drive.l || R.drive.r ? 'MANUAL' : 'IDLE';
      return ok();
    case 'move':
      return ok(await motion(async (t) => { await forward(+p.distance_m || 0, t); return { moved_m: +p.distance_m || 0 }; }));
    case 'turn':
      return ok(await motion(async (t) => { await turnBy(+p.angle_deg || 0, t); return { turned_deg: +p.angle_deg || 0 }; }));
    case 'go_to_zone':
      return ok(await motion(async (t) => { await goToZone(p.zone, t); return { zone: p.zone, arrived: true }; }));
    case 'go_to_point':
      return ok(await motion(async (t) => { await goTo(+p.x, +p.y, t); return { x: +p.x, y: +p.y }; }));
    case 'set_home':
      R.x = 0; R.y = 0; R.h = 0;
      return ok();
    case 'stop':
      R.cancel++; R.drive = { l: 0, r: 0, at: 0 }; R.state = 'IDLE';
      return ok();
    case 'estop':
      R.cancel++; R.estop = true; R.drive = { l: 0, r: 0, at: 0 }; R.stopCount++;
      emit({ kind: 'events', robot_id: RID, data: { type: 'event', event: 'estop', ts: now(), data: { source: 'app' } } });
      return ok();
    case 'reset':
      R.estop = false; R.state = 'IDLE';
      return ok();
    case 'pan_tilt': {
      // budget robot: no servos, the whole robot turns to look and turns back for pan 0
      const target = Math.max(-90, Math.min(90, +p.pan || 0));
      R.h += target - R.pan; R.pan = target; R.tilt = 0;
      return ok({ pan: R.pan, tilt: 0, fixed_camera: true });
    }
    case 'snapshot':
      if (R.privacy) return { ...ok(), status: 'rejected', error: 'privacy mode is on' };
      return ok({ zone: zoneAt(), image_b64: frameUri().split(',')[1] });
    case 'read_environment':
      return ok(room().environment ?? room().telemetry.environment);
    case 'listen_audio':
      return ok(room().telemetry.audio ?? { label: 'quiet', title: 'Quiet room', confidence: 0.9, db: 36, method: 'demo' });
    case 'set_privacy':
      R.privacy = !!p.enabled;
      return ok({ privacy_mode: R.privacy });
    case 'speak':
      return ok({ spoken: String(p.text ?? '') });
    case 'ping':
      return ok({ robot_ts: now() });
    case 'status':
      return ok(telemetry());
    case 'recheck_hardware':
      return ok({ restarting: false, health: telemetry().health, faults: [] });
    default:
      return { ...ok(), status: 'error', error: `'${action}' needs the real robot (this is the demo)` };
  }
}

// ------------------------------------------------------------------ pictures
function frameUri(): string {
  const z = near();
  const key = `frame_${z}_${Math.abs(R.pan) > 15 ? 35 : 0}`;
  return DEMO_IMAGES[key] ?? DEMO_IMAGES[`frame_${z}_0`] ?? Object.values(DEMO_IMAGES)[0];
}
export function demoAsset(path: string): string {
  if (path.includes('/frame.jpg')) return frameUri();
  const m = /\/images\/([^?]+)/.exec(path);
  if (m && DEMO_IMAGES[decodeURIComponent(m[1])]) return DEMO_IMAGES[decodeURIComponent(m[1])];
  return frameUri();
}

// ------------------------------------------------------------------ reports
const REPORTS: { item: ReportListItem; report: InspectionReport }[] = Object.values(D.reports as Record<string, any>)
  .map((r: any) => clone(r))
  .sort((a: any, b: any) => b.item.created - a.item.created);
{
  // recorded minutes ago in the simulator: show them as this morning's patrol
  const shift = now() - 3 * 3600 - (REPORTS[0]?.item.created ?? now());
  REPORTS.forEach((r) => { r.item.created += shift; r.report.created += shift; r.report.zones.forEach((z) => { z.ts += shift; }); });
}
const ZONE_INSPECTION: Record<string, ZoneInspection> = {};
[...REPORTS].reverse().forEach((r) => r.report.zones.forEach((z) => { ZONE_INSPECTION[z.zone] = z; }));

function newReport(zones: string[], request: string): InspectionReport {
  const id = uid();
  const t = now();
  const zs = zones.map((z) => ({ ...clone(ZONE_INSPECTION[z]), id: uid(), ts: t }));
  const issues = zs.reduce((n, z) => n + z.anomalies.length, 0);
  const md = [`# Inspection report`, '', `**Request:** ${request}`, '',
    ...zs.flatMap((z) => [`## ${nice(z.zone)}`, '', z.summary, '', ...z.recommended_actions.map((a) => `- **${a.priority}** ${a.action}`), ''])].join('\n');
  const report: InspectionReport = { id, created: t, robot_id: RID, request, zones: zs, title: `Inspection: ${zones.map(nice).join(', ')}`, markdown: md };
  REPORTS.unshift({ item: { id, created: t, robot_id: RID, request, zones, compliant: zs.every((z) => z.compliant) }, report });
  void issues;
  return report;
}

// ------------------------------------------------------------------ chat agent (rule based, like the offline planner)
const ZONE_WORDS: [RegExp, string][] = [
  [/\b(iot|lab|laboratory)\b/i, 'IoT_Lab'],
  [/\b(hall|lecture hall|room)\s*b\b/i, 'LectureHall_B'],
  [/\b(hall|lecture hall|room)\s*a\b/i, 'LectureHall_A'],
  [/\bexam/i, 'Exam_Hall'],
  [/\b(home|base|dock|charg)/i, 'Home'],
];
const zonesIn = (s: string) => ZONE_WORDS.filter(([re]) => re.test(s)).map(([, z]) => z);
const plain = (md: string) => md.replace(/[*#_`>]/g, '').replace(/⚠️|✅/g, '').replace(/\s+\n/g, '\n').trim();

async function runSteps(steps: AgentStep[], work: (i: number) => Promise<string>) {
  emit({ kind: 'agent', robot_id: RID, data: { type: 'plan', steps: clone(steps), ack: null } });
  for (let i = 0; i < steps.length; i++) {
    steps[i] = { ...steps[i], status: 'running' };
    emit({ kind: 'agent', robot_id: RID, data: { type: 'step', index: i, step: clone(steps[i]) } });
    try {
      steps[i] = { ...steps[i], status: 'done', summary: await work(i) };
    } catch (e: any) {
      steps[i] = { ...steps[i], status: 'error', summary: e?.message ?? String(e) };
      emit({ kind: 'agent', robot_id: RID, data: { type: 'step', index: i, step: clone(steps[i]) } });
      throw e;
    }
    emit({ kind: 'agent', robot_id: RID, data: { type: 'step', index: i, step: clone(steps[i]) } });
  }
}

function reply(text: string, steps: AgentStep[], t0: number, extra: Partial<ChatResponse> = {}): ChatResponse {
  return { reply: text, steps: clone(steps), report_id: null, planner: 'demo', duration_s: +(now() - t0).toFixed(1), speech: plain(text), ack: null, images: [], ...extra };
}

const ROOMS = ['IoT_Lab', 'LectureHall_B', 'LectureHall_A', 'Exam_Hall'];

async function goHome(steps: AgentStep[]) {
  const i = steps.length;
  steps.push({ tool: 'return_home', args: {}, status: 'running', summary: '' });
  emit({ kind: 'agent', robot_id: RID, data: { type: 'step', index: i, step: clone(steps[i]) } });
  await motion((t) => goToZone('Home', t));
  steps[i] = { ...steps[i], status: 'done', summary: 'back at the dock' };
  emit({ kind: 'agent', robot_id: RID, data: { type: 'step', index: i, step: clone(steps[i]) } });
}

async function chat(message: string): Promise<ChatResponse> {
  const t0 = now();
  const m = message.toLowerCase();
  const zs = zonesIn(m);
  const rooms = zs.filter((z) => z !== 'Home');
  const all = /\b(all|every|each)\b/.test(m);
  const andHome = /(return|go|come) (back )?(home|to the dock|to base)|then (home|dock)/.test(m);
  const rec = (k: string) => D.chats[k]?.response as ChatResponse | undefined;

  if (/(who is talking|someone.*talk|talking|noise)/.test(m)) {
    const steps: AgentStep[] = [{ tool: 'sound_scan', args: {}, status: 'pending', summary: '' }];
    const inc = (D.sessions?.[0]?.incidents ?? [])[0];
    await runSteps(steps, async () => {
      await motion(async (t) => { if (!zoneAt() || zoneAt() !== 'Exam_Hall') await goToZone('Exam_Hall', t); await turnBy(360, t); await turnBy(48, t); await forward(0.7, t); });
      return 'loudest voice found';
    });
    return reply(inc?.summary ?? 'Someone is talking ahead on the left, I moved 0.7 m toward them. I asked them to stop talking.', steps, t0);
  }
  if (/^(stop|halt|freeze)\b|\bstop (now|moving|the robot)\b/.test(m)) {
    await command('stop', {});
    return reply('Stopped.', [], t0);
  }
  if (/(air ?con|a\.?c\b|aircon|air-conditioner|cooling)/.test(m)) {
    const targets = rooms.length && !all ? rooms : ['IoT_Lab', 'LectureHall_B', 'LectureHall_A'];
    const steps: AgentStep[] = targets.map((z) => ({ tool: 'check_ac', args: { zone: z }, status: 'pending', summary: '' }));
    const lines: string[] = [];
    await runSteps(steps, async (i) => {
      const z = targets[i];
      await motion((t) => goToZone(z, t));
      const env = room(z).environment ?? room(z).telemetry.environment;
      const line = z === 'LectureHall_B' && rec('aircon_hallb') ? rec('aircon_hallb')!.reply
        : `${nice(z)}: ${env?.temperature_c?.toFixed(1)}°C, ${Math.round(env?.humidity_pct ?? 0)}% humidity (${String(env?.comfort_verdict ?? '').replace(/_/g, ' ').toLowerCase()}).`;
      lines.push(line);
      return line;
    });
    if (andHome) await goHome(steps);
    return reply(lines.join('\n\n'), steps, t0, { ack: `On it. I'll check the air-conditioning in ${targets.map(nice).join(', ')}.` });
  }
  if (/(show me|search|history|last (week|month|year)|when was|unhealthy|over the past)/.test(m) && !/(inspect|patrol|what did you find)/.test(m)) {
    const res = search(message);
    const top = (res.results as any[]).slice(0, 4);
    const text = top.length ? `I found ${res.results.length} records. The closest matches:\n\n` + top.map((h) => `- ${h.text.slice(0, 160)}`).join('\n')
      : 'I found nothing like that in my inspection memory.';
    return reply(text, [{ tool: 'search_memory', args: { query: message }, status: 'done', summary: `${res.results.length} records` }], t0);
  }
  if (/(what did you find|last (report|inspection)|findings)/.test(m) && !/what.*see/.test(m)) {
    const last = REPORTS[0];
    if (!last) return reply("I haven't inspected anything yet. Say \"inspect the IoT lab\".", [], t0);
    const z = last.report.zones.find((x) => !rooms.length || rooms.includes(x.zone)) ?? last.report.zones[0];
    const issues = z.anomalies.length ? `${z.anomalies.length} issues: ${z.anomalies.map((a) => a.description.toLowerCase()).join('; ')}.` : 'no issues.';
    return reply(`In my last inspection, ${nice(z.zone)} had ${issues}`, [{ tool: 'last_findings', args: {}, status: 'done', summary: z.zone }], t0, { report_id: last.item.id });
  }
  if (/(monitor|proctor|watch).*(exam)|exam.*(monitor|watch)/.test(m)) {
    const mins = Number((m.match(/(\d+)\s*(min|minute)/) ?? [])[1] ?? 30);
    await monitorStart({ zone: 'Exam_Hall', minutes: mins, mode: 'patrol' });
    return reply(`Exam monitoring started in Exam Hall for ${mins} minutes. Open More > Exam monitoring to watch it live.`, [], t0,
      { ack: "On it. I'll watch the exam." });
  }
  if (/(inspect|audit|check|patrol|survey)/.test(m)) {
    const targets = (rooms.length && !all ? rooms : ROOMS).filter((z) => ZONE_INSPECTION[z]);
    const steps: AgentStep[] = targets.map((z) => ({ tool: 'inspect_zone', args: { zone: z }, status: 'pending', summary: '' }));
    await runSteps(steps, async (i) => {
      await motion(async (t) => {
        await goToZone(targets[i], t);
        for (const pan of [-35, 35, 0]) { R.h += pan - R.pan; R.pan = pan; await sleep(500); }   // fixed camera: the robot turns
      });
      const zi = ZONE_INSPECTION[targets[i]];
      return `${targets[i]}: ${zi.anomalies.length} issue(s)${zi.anomalies.length ? ' - ' + zi.anomalies.map((a) => a.description).join('; ') : ''}`;
    });
    if (andHome) await goHome(steps);
    const rep = newReport(targets, message);
    const key = targets.join(',') === 'IoT_Lab,LectureHall_B' ? 'inspect_lab_hallb' : targets.join(',') === 'LectureHall_A' ? 'inspect_halla'
      : targets.join(',') === 'Exam_Hall' ? 'inspect_exam' : '';
    const issues = rep.zones.reduce((n, z) => n + z.anomalies.length, 0);
    const text = key && rec(key) ? rec(key)!.reply
      : `Inspected **${targets.length} room${targets.length > 1 ? 's' : ''}** - ${issues ? `**${issues} findings** to act on.` : 'everything is compliant.'}\n\n`
        + rep.zones.map((z) => z.anomalies.length
          ? `⚠️ **${nice(z.zone)}** - ${z.anomalies.length} issue${z.anomalies.length > 1 ? 's' : ''}:\n` + z.anomalies.map((a) => `- ${a.description}`).join('\n')
          : `✅ **${nice(z.zone)}** - all clear.`).join('\n\n')
        + '\n\nThe full audit report is saved in Reports.';
    return reply(text, steps, t0, { report_id: rep.id, ack: `On it. I'll inspect ${targets.map(nice).join(', ')}.` });
  }
  if (/(go|drive|head|take me|move|return|come) (back )?(to|home)\b/.test(m) && zs.length) {
    const z = rooms[0] ?? 'Home';
    const steps: AgentStep[] = [{ tool: 'go_to_zone', args: { zone: z }, status: 'pending', summary: '' }];
    await runSteps(steps, async () => { await motion((t) => goToZone(z, t)); return `arrived at ${nice(z)}`; });
    return reply(z === 'Home' ? "I'm back at the dock." : `I'm in ${nice(z)}.`, steps, t0);
  }
  // relative moves, possibly chained: "turn around, go forward 1 meter and tell me what you see"
  const parts = m.split(/,|\bthen\b|\band\b/).map((x) => x.trim()).filter(Boolean);
  const plan: { tool: string; args: any; text: string }[] = [];
  for (const x of parts) {
    let mm: RegExpMatchArray | null;
    if ((mm = x.match(/(forward|ahead|back|backward|backwards|reverse)\s*(\d+(?:\.\d+)?)?\s*(cm|centimet\w*|m\b|met\w*)?/))) {
      let d = mm[2] ? parseFloat(mm[2]) : 0.5;
      if (mm[3] && mm[3].startsWith('c')) d /= 100;
      if (/back|reverse/.test(mm[1])) d = -d;
      plan.push({ tool: 'move', args: { distance_m: d }, text: `Moved ${d < 0 ? 'back' : 'forward'} ${Math.abs(d) < 1 ? Math.round(Math.abs(d) * 100) + ' cm' : Math.abs(d) + ' m'}.` });
    } else if ((mm = x.match(/turn\s*(left|right|around)?\s*(\d+)?/))) {
      const a = mm[1] === 'around' ? 180 : (mm[2] ? parseFloat(mm[2]) : 90) * (mm[1] === 'right' ? -1 : 1);
      plan.push({ tool: 'turn', args: { angle_deg: a }, text: a === 180 ? 'Turned around.' : `Turned ${a > 0 ? 'left' : 'right'} ${Math.abs(a)}°.` });
    } else if (/(what.*see|describe|look around|picture|photo|camera|what it is)/.test(x)) {
      if (!plan.some((p) => p.tool === 'capture_and_analyze')) plan.push({ tool: 'capture_and_analyze', args: {}, text: '' });
    }
  }
  if (plan.length) {
    const steps: AgentStep[] = plan.map((p) => ({ tool: p.tool, args: p.args, status: 'pending', summary: '' }));
    const said: string[] = [];
    await runSteps(steps, async (i) => {
      const p = plan[i];
      if (p.tool === 'move') await motion((t) => forward(p.args.distance_m, t));
      else if (p.tool === 'turn') await motion((t) => turnBy(p.args.angle_deg, t));
      else {
        const zi = ZONE_INSPECTION[near()];
        const desc = (zi?.vision?.description ?? '').replace(/^\[[^\]]*\]\s*/, '').replace(/^In \w+:\s*/, '').replace(/^I see /i, '');
        p.text = desc ? `I'm in ${nice(near())}. I see ${desc}` : `I'm in ${nice(zoneAt())}. The corridor ahead is clear.`;
      }
      said.push(p.text);
      return p.text;
    });
    return reply(said.join(' '), steps, t0);
  }
  if (/(battery|status|where are you|how are you)/.test(m)) {
    return reply(`I'm in ${nice(zoneAt())}, battery ${Math.round(R.battery)}%, everything working. (Demo robot inside this phone.)`, [], t0);
  }
  return reply('In the demo I understand: "inspect the IoT lab", "patrol all rooms", "check the aircon in hall B", "go to lecture hall A", '
    + '"move forward 1 meter", "turn left", "what do you see", "what did you find", "who is talking", "monitor the exam" and "battery".', [], t0);
}

// ------------------------------------------------------------------ exam monitoring
const SESSIONS: ExamSession[] = (D.sessions ?? []).map((s: any) => {
  const c = clone(s);
  const shift = now() - 2 * 3600 - c.started;
  c.started += shift; c.ended = (c.ended ?? c.ends_at ?? c.started + c.minutes * 60) + shift;
  c.incidents = (c.incidents ?? []).map((i: any) => ({ ...i, ts: i.ts + shift }));
  c.stop_reason = 'time is up';
  return c;
});
let live: (MonitorStatus & { t0: number }) | null = null;

async function monitorStart(b: any): Promise<MonitorStatus> {
  if (live?.active) throw new DemoError(409, 'Monitoring is already running');
  const minutes = Math.max(1, Math.min(180, +b.minutes || 2));
  const t = now();
  live = { active: true, id: uid(), zone: b.zone ?? 'Exam_Hall', started: t, ends_at: t + minutes * 60, minutes, mode: b.mode ?? 'patrol',
    sensitivity: b.sensitivity ?? 'normal', incidents: [], views: 0, rounds: 0, phase: 'driving', t0: t, baseline_db: 35,
    detect: b.detect, route: D.monitor_live?.[3]?.route, vision: 'demo' } as any;
  void motion((tok) => goToZone(live!.zone ?? 'Exam_Hall', tok)).catch(() => {});
  return monitorStatus();
}

function monitorStatus(): MonitorStatus {
  if (!live) return { active: false, text: 'No exam monitoring is running.' } as MonitorStatus;
  const t = now();
  if (live.active && t >= (live.ends_at ?? t)) {
    live.active = false;
    live.phase = 'finished';
    const s: ExamSession = { id: live.id!, zone: live.zone ?? null, started: live.started!, ended: t, minutes: live.minutes!, mode: live.mode!,
      incidents: live.incidents, incident_count: live.incidents?.length, stop_reason: 'time is up', vision: 'demo', views: live.views };
    SESSIONS.unshift(s);
  }
  if (live.active) {
    const frames: any[] = D.monitor_live ?? [];
    const k = Math.min(frames.length - 1, Math.floor((t - live.t0) / ((live.minutes! * 60) / Math.max(1, frames.length))));
    const f = frames[Math.max(0, k)] ?? {};
    const rec = (D.sessions?.[0]?.incidents ?? []) as any[];
    if (rec.length && !live.incidents!.length && t - live.t0 > Math.min(50, live.minutes! * 25)) {
      live.incidents = rec.map((i) => ({ ...i, ts: t }));
      emit({ kind: 'events', robot_id: RID, data: { type: 'event', event: 'exam_incident', ts: t, data: { title: rec[0].title, summary: rec[0].summary } } });
    }
    live.phase = f.phase === 'finished' ? 'watching' : f.phase ?? 'watching';
    live.views = Math.floor((t - live.t0) / 6);
    live.view_pan = f.view_pan ?? 0;
    live.view_dir = f.view_dir ?? 0;
    live.waypoint = f.waypoint ?? 1;
    live.level_db = 36 + Math.round(Math.random() * 6);
  }
  const left = Math.max(0, Math.ceil(((live.ends_at ?? t) - t) / 60));
  const n = live.incidents?.length ?? 0;
  live.minutes_left = left;
  live.text = live.active
    ? `I'm monitoring ${nice(live.zone)}, ${left} minute${left === 1 ? '' : 's'} left. ${n ? `I flagged ${n} incident${n > 1 ? 's' : ''}.` : 'Everything has been fine so far.'}`
    : `The last monitoring session in ${nice(live.zone)} has ended. ${n ? `I flagged ${n} incident${n > 1 ? 's' : ''}.` : 'Nothing was flagged.'}`;
  const { t0: _t0, ...out } = live;
  return clone(out);
}

// ------------------------------------------------------------------ users, schedules, AI
const USERS: UserAccount[] = clone(D.users);
const PASSWORDS: Record<string, string> = { admin: 'admin123', operator: 'operator123', viewer: 'viewer123' };
let me: UserAccount | null = null;
const SCHEDULES: Schedule[] = [{
  id: 'demo-morning', name: 'Morning energy check', command: 'Inspect the IoT lab and lecture hall B', time: '08:00', days: [0, 1, 2, 3, 4],
  enabled: true, robot_id: RID, created_by: 'admin', last_run: null, last_status: null, last_report: null,
}];

function history() {
  const rec: any[] = D.history ?? [];
  const out = [];
  const t = now();
  for (let i = 0; i < 90; i++) {
    const r = rec[i % Math.max(1, rec.length)] ?? {};
    out.push({ ...r, ts: t - (90 - i) * 10, battery: Math.round(R.battery + (90 - i) * 0.01) });
  }
  return out;
}

function mapNow() {
  const m = clone(D.map);
  m.pose = { x: R.x, y: R.y, heading_deg: R.h, zone: zoneAt() };
  m.status = {};
  for (const r of [...REPORTS].reverse()) {
    for (const z of r.report.zones) {
      const issues = z.anomalies.length;
      m.status[z.zone] = { level: issues === 0 ? 'ok' : z.anomalies.some((a) => a.severity === 'high' || a.severity === 'critical') ? 'alert' : 'warn',
        issues, report_id: r.item.id, ts: z.ts, compliant: z.compliant, comfort: z.comfort_verdict, gas: z.gas_verdict,
        energy: z.energy_status, safety: z.safety_status };
    }
  }
  return m;
}

function health() {
  const h = clone(D.health);
  h.site = 'Demo robot (inside this phone)';
  h.robots = { [RID]: { robot_id: RID, online: true, state: R.state, simulation: true, zone: zoneAt(), zones: Object.keys(ZONES) } };
  h.planner = 'demo';
  h.stt = 'none';
  h.warnings = [];
  h.demo = true;
  return h;
}

function search(q: string) {
  const all: Record<string, any> = D.search ?? {};
  const key = Object.keys(all).find((k) => q.toLowerCase().includes(k.split(' ')[0])) ?? Object.keys(all)[0];
  const words = q.toLowerCase().split(/\W+/).filter((w) => w.length > 2);
  const pool = Object.values(all).flatMap((r: any) => r.results);
  const hits = words.length ? pool.filter((h: any) => words.some((w) => h.text.toLowerCase().includes(w))) : [];
  const res = clone(all[key] ?? { results: [] });
  res.query = q;
  res.results = (hits.length ? hits : res.results).slice(0, 10);
  res.took_ms = 4;
  return res;
}

function reportHtml(r: InspectionReport) {
  const body = r.markdown
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>').replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^- (.*)$/gm, '<li>$1</li>').replace(/\n\n/g, '<br/>');
  return `<!doctype html><html><head><meta charset="utf-8"><title>${r.title}</title><style>body{font-family:sans-serif;padding:24px;color:#14232E}h1{font-size:22px}h2{font-size:17px;margin-top:20px}</style></head><body>${body}<p style="color:#888;font-size:12px">Raqib demo robot</p></body></html>`;
}

// ------------------------------------------------------------------ the API router
export async function demoRequest(path: string, init: RequestInit = {}): Promise<any> {
  const method = (init.method ?? 'GET').toUpperCase();
  const body = init.body ? JSON.parse(String(init.body)) : {};
  const [p, qs] = path.split('?');
  const q = new URLSearchParams(qs ?? '');
  startTicker();
  await sleep(60);
  let mm: RegExpMatchArray | null;

  if (p === '/health') return health();
  if (p === '/auth/login') {
    const u = USERS.find((x) => x.username === String(body.username ?? '').trim().toLowerCase());
    if (!u || (PASSWORDS[u.username] ?? '') !== body.password) throw new DemoError(401, 'Wrong username or password (demo: admin / admin123)');
    me = u;
    return { access_token: `demo-${u.username}`, role: u.role, username: u.username, name: u.name };
  }
  if (p === '/auth/password') { if (me) PASSWORDS[me.username] = body.new_password; return { ok: true }; }
  if (p === '/robots') return Object.values(health().robots);
  if ((mm = p.match(/^\/robots\/[^/]+$/))) return { online: true, telemetry: telemetry(), info: info() };
  if ((mm = p.match(/^\/robots\/[^/]+\/command$/))) return command(body.action, body.params ?? {});
  if (p.endsWith('/estop')) return command('estop', {});
  if (p.endsWith('/reset')) return command('reset', {});
  if (p.endsWith('/ping')) return { median_ms: 2, samples: [2, 2, 3] };
  if (p.endsWith('/history')) return history();
  if (p.endsWith('/map')) return mapNow();
  if (p === '/chat' && method === 'POST') return chat(String(body.message ?? ''));
  if (p === '/chat/history') return [];
  if (p === '/reports') return REPORTS.map((r) => r.item);
  if ((mm = p.match(/^\/reports\/([^/]+)$/))) {
    const r = REPORTS.find((x) => x.item.id === mm![1]);
    if (!r) throw new DemoError(404, 'report not found');
    return r.report;
  }
  if (p === '/search') return search(q.get('q') ?? '');
  if (p === '/memory/seed') return { added: 0 };
  if (p === '/users' && method === 'GET') return USERS;
  if (p === '/users' && method === 'POST') {
    const u: UserAccount = { username: body.username, role: body.role, name: body.name ?? body.username, created: now(), disabled: false, last_login: null };
    USERS.push(u); PASSWORDS[u.username] = body.password;
    return u;
  }
  if ((mm = p.match(/^\/users\/([^/]+)$/))) {
    const name = decodeURIComponent(mm[1]);
    const i = USERS.findIndex((x) => x.username === name);
    if (method === 'DELETE') { if (i >= 0) USERS.splice(i, 1); return { ok: true }; }
    if (i >= 0) { Object.assign(USERS[i], body); if (body.password) PASSWORDS[name] = body.password; }
    return USERS[i];
  }
  if (p === '/monitor' && method === 'GET') return monitorStatus();
  if (p === '/monitor/start') return monitorStart(body);
  if (p === '/monitor/stop') {
    if (live?.active) live.ends_at = now() - 1;
    monitorStatus();
    return { text: 'Exam monitoring stopped.' };
  }
  if (p === '/monitor/sessions') return SESSIONS.map(({ incidents, ...s }) => ({ ...s, incident_count: incidents?.length ?? 0 }));
  if ((mm = p.match(/^\/monitor\/sessions\/([^/]+)$/))) return SESSIONS.find((s) => s.id === mm![1]) ?? SESSIONS[0];
  if (p === '/monitor/capabilities') return { ...D.caps, text: 'Demo: replays a real monitoring session from the simulator.' };
  if (p === '/schedules' && method === 'GET') return SCHEDULES;
  if (p === '/schedules' && method === 'POST') {
    const s: Schedule = { id: uid(), enabled: true, robot_id: RID, created_by: me?.username ?? 'admin', last_run: null, last_status: null, last_report: null, ...body };
    SCHEDULES.push(s);
    return s;
  }
  if ((mm = p.match(/^\/schedules\/([^/]+)\/enabled$/))) { const s = SCHEDULES.find((x) => x.id === mm![1]); if (s) s.enabled = q.get('enabled') === 'true'; return s; }
  if ((mm = p.match(/^\/schedules\/([^/]+)\/run$/))) {
    const s = SCHEDULES.find((x) => x.id === mm![1]);
    if (!s) throw new DemoError(404, 'schedule not found');
    const r = await chat(s.command);
    s.last_run = now(); s.last_status = 'ok'; s.last_report = r.report_id;
    return { ok: true, report_id: r.report_id, reply: r.reply };
  }
  if ((mm = p.match(/^\/schedules\/([^/]+)$/)) && method === 'DELETE') { const i = SCHEDULES.findIndex((x) => x.id === mm![1]); if (i >= 0) SCHEDULES.splice(i, 1); return { ok: true }; }
  if (p === '/admin/ai' && method === 'GET') return D.ai;
  if (p === '/admin/ai') return { ...D.ai, saved: false };
  if (p === '/admin/ai/test') return { ok: false, error: 'The demo robot has no AI key. Connect to your robot to use Gemini or OpenAI.' };
  if (p === '/webrtc/offer') throw new DemoError(503, 'no live video in the demo');
  throw new DemoError(404, `${p} is not available in the demo`);
}

export function demoText(path: string): string {
  let mm: RegExpMatchArray | null;
  if ((mm = path.match(/^\/reports\/([^/]+)\/print/))) {
    const r = REPORTS.find((x) => x.item.id === mm![1]) ?? REPORTS[0];
    return reportHtml(r.report);
  }
  if ((mm = path.match(/^\/monitor\/sessions\/([^/]+)\/print/))) {
    const s = SESSIONS.find((x) => x.id === mm![1]) ?? SESSIONS[0];
    const rows = (s?.incidents ?? []).map((i) => `<li>${new Date(i.ts * 1000).toLocaleTimeString()} - <b>${i.title}</b>: ${i.summary}</li>`).join('');
    return `<!doctype html><html><head><meta charset="utf-8"><title>Exam monitoring</title></head><body style="font-family:sans-serif;padding:24px"><h1>Exam monitoring - ${nice(s?.zone)}</h1><ul>${rows || '<li>No incidents.</li>'}</ul><p style="color:#888;font-size:12px">Raqib demo robot</p></body></html>`;
  }
  return '<p>Not available in the demo.</p>';
}

/** Live link (replaces the WebSocket in demo mode). Returns a function that disconnects. */
export function demoConnect(onMessage: (m: ServerMessage) => void): () => void {
  listeners.add(onMessage);
  startTicker();
  setTimeout(() => {
    onMessage({ kind: 'status', robot_id: RID, data: { online: true } });
    onMessage({ kind: 'info', robot_id: RID, data: info() as any });
    onMessage({ kind: 'telemetry', robot_id: RID, data: telemetry() });
  }, 50);
  return () => { listeners.delete(onMessage); };
}
