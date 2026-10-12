// Safety alerts: haptic + local notification (phone) + in-app banner.
import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

import { alertActions, store } from '@/store';
import { ZONE_LABEL } from '@/theme';
import type { RobotEvent } from '@/types';

let Notifications: typeof import('expo-notifications') | null = null;
if (Platform.OS !== 'web') {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    Notifications = require('expo-notifications');
    Notifications!.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
  } catch {
    Notifications = null;
  }
}

export async function requestAlertPermission(): Promise<boolean> {
  if (!Notifications) return false;
  try {
    const cur = await Notifications.getPermissionsAsync();
    if (cur.granted) return true;
    const res = await Notifications.requestPermissionsAsync();
    return res.granted;
  } catch {
    return false;
  }
}

const MESSAGES: Record<string, (d: any) => { title: string; body: string; level: 'warn' | 'alert' | 'ok'; reportId?: string; route?: string } | null> = {
  talking_detected: (d) => ({
    title: `Talking in ${d.zone ? ZONE_LABEL(d.zone) : 'the exam'}`,
    body: d.summary ?? 'Someone was talking. The robot asked them to stop.',
    level: 'warn',
    route: '/monitor',
  }),
  proctor_flag: (d) => ({
    title: `${d.title ?? 'Incident'} in ${d.zone ? ZONE_LABEL(d.zone) : 'the exam'}`,
    body: d.summary ?? 'The robot flagged a student and took a photo.',
    level: ['phone', 'notes', 'earpiece'].includes(d.type) ? 'alert' : 'warn',
    route: '/monitor',
  }),
  monitoring_finished: (d) => ({
    title: 'Exam monitoring finished',
    body: d.incidents ? `${d.incidents} incident${d.incidents > 1 ? 's' : ''} in ${ZONE_LABEL(d.zone)}. Open the monitor for photos and the PDF report.` : `No incidents in ${ZONE_LABEL(d.zone)}.`,
    level: d.incidents ? 'warn' : 'ok',
    route: '/monitor',
  }),
  gas_alert: (d) => ({
    title: d.gas_verdict === 'HAZARD' ? 'Hazardous air detected' : 'Poor air quality',
    body: `AQI ${Math.round(d.aqi ?? 0)} in ${d.zone ?? 'the corridor'}. Ventilate the room.`,
    level: d.gas_verdict === 'HAZARD' ? 'alert' : 'warn',
  }),
  obstacle_stop: (d) => ({
    title: 'Obstacle - robot stopped',
    body: `Something is ${Math.round(d.distances_cm?.center ?? 0)} cm ahead. Stopped in ${d.latency_ms} ms.`,
    level: 'warn',
  }),
  safe_hold: () => ({ title: 'Robot in safe hold', body: 'The robot lost its connection to the server and stopped.', level: 'alert' }),
  inspection_complete: (d) =>
    d.issues
      ? { title: d.schedule ? `${d.schedule} finished` : 'Inspection finished', body: `${d.issues} finding${d.issues > 1 ? 's' : ''} in ${(d.zones ?? []).map(ZONE_LABEL).join(' and ')}. Open Reports for details.`, level: 'warn', reportId: d.report_id }
      : { title: d.schedule ? `${d.schedule} finished` : 'Inspection finished', body: `${(d.zones ?? []).map(ZONE_LABEL).join(' and ')}: all clear.`, level: 'ok', reportId: d.report_id },
  low_battery: (d) => ({ title: 'Battery low', body: `${Math.round(d.percent ?? 0)}% left. Return the robot to charge.`, level: 'warn' }),
};

const lastShown: Record<string, number> = {};

export function handleRobotEvent(e: RobotEvent) {
  const make = MESSAGES[e.event];
  if (!make) return;
  const msg = make(e.data);
  if (!msg) return;
  const now = Date.now();
  if (e.event !== 'talking_detected' && e.event !== 'proctor_flag' && now - (lastShown[e.event] ?? 0) < 15000) return; // de-duplicate bursts
  lastShown[e.event] = now;
  store.dispatch(alertActions.push({ id: `${e.event}-${now}`, ...msg, ts: now }));
  if (Platform.OS !== 'web') {
    Haptics.notificationAsync(msg.level === 'alert' ? Haptics.NotificationFeedbackType.Error : msg.level === 'ok' ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Warning).catch(() => {});
  }
  if (Notifications && store.getState().session.notifications) {
    Notifications.scheduleNotificationAsync({ content: { title: msg.title, body: msg.body }, trigger: null }).catch(() => {});
  }
}
