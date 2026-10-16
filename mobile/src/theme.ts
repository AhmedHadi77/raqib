// Raqib design tokens.
// Navy ink + signal blue come from the logo; cyan = the robot / live data; amber is reserved for findings.
import { configureFonts, MD3DarkTheme, MD3LightTheme } from 'react-native-paper';

export const APP_VERSION = '2.5.1';

export const BRAND = {
  name: 'Raqib',
  tagline: 'Autonomous facility inspection',
  navy: '#0D1530',
  navy2: '#16224A',
  navyLine: '#24325C',
  blue: '#3D63FF',
  cyan: '#1FC8E3',
  amber: '#FFB224',
};

export const fonts = {
  display: 'Archivo_800ExtraBold',
  heading: 'Archivo_700Bold',
  numeric: 'Archivo_600SemiBold',
  body: 'PublicSans_400Regular',
  bodyMedium: 'PublicSans_500Medium',
  bodyStrong: 'PublicSans_600SemiBold',
};

export interface Palette {
  dark: boolean;
  paper: string;
  surface: string;
  sunken: string;
  ink: string;
  inkSoft: string;
  inkFaint: string;
  line: string;
  primary: string;
  primarySoft: string;
  onPrimary: string;
  cyan: string;
  amber: string;
  amberSoft: string;
  danger: string;
  dangerSoft: string;
  info: string;
  ok: string;
  okSoft: string;
  // console surfaces (map, drive) stay navy in both themes
  console: string;
  console2: string;
  consoleLine: string;
  consoleInk: string;
  consoleSoft: string;
}

export const light: Palette = {
  dark: false,
  paper: '#F4F6FA',
  surface: '#FFFFFF',
  sunken: '#EAEEF5',
  ink: '#0D1530',
  inkSoft: '#56607A',
  inkFaint: '#8A93A8',
  line: '#DDE2EC',
  primary: '#3D63FF',
  primarySoft: '#E5EBFF',
  onPrimary: '#FFFFFF',
  cyan: '#0FA9C7',
  amber: '#B87300',
  amberSoft: '#FFF0D3',
  danger: '#D63B3B',
  dangerSoft: '#FCE6E6',
  info: '#3D63FF',
  ok: '#13905C',
  okSoft: '#DCF4E9',
  console: BRAND.navy,
  console2: BRAND.navy2,
  consoleLine: BRAND.navyLine,
  consoleInk: '#EEF2FF',
  consoleSoft: '#95A2C6',
};

export const dark: Palette = {
  dark: true,
  paper: '#080D1D',
  surface: '#101831',
  sunken: '#172242',
  ink: '#E9EDF8',
  inkSoft: '#9AA6C2',
  inkFaint: '#6B7898',
  line: '#212D50',
  primary: '#7C95FF',
  primarySoft: '#1B2758',
  onPrimary: '#071029',
  cyan: '#38D6EE',
  amber: '#FFB224',
  amberSoft: '#3A2B0C',
  danger: '#FF6B6B',
  dangerSoft: '#3E1A20',
  info: '#7C95FF',
  ok: '#3DD598',
  okSoft: '#0F3628',
  console: '#0B1229',
  console2: '#121C3D',
  consoleLine: '#222F58',
  consoleInk: '#EEF2FF',
  consoleSoft: '#8E9BC0',
};

function paperTheme(base: typeof MD3LightTheme, p: Palette) {
  return {
    ...base,
    roundness: 3,
    fonts: configureFonts({ config: { fontFamily: fonts.body } }),
    colors: {
      ...base.colors,
      primary: p.primary,
      onPrimary: p.onPrimary,
      primaryContainer: p.primarySoft,
      onPrimaryContainer: p.ink,
      secondary: p.inkSoft,
      secondaryContainer: p.primarySoft,
      onSecondaryContainer: p.ink,
      tertiary: p.amber,
      error: p.danger,
      background: p.paper,
      surface: p.surface,
      surfaceVariant: p.sunken,
      onSurface: p.ink,
      onSurfaceVariant: p.inkSoft,
      outline: p.line,
      outlineVariant: p.line,
      backdrop: 'rgba(8,13,29,0.55)',
      elevation: { ...base.colors.elevation, level1: p.surface, level2: p.surface, level3: p.surface },
    },
    palette: p,
  };
}

export const lightTheme = paperTheme(MD3LightTheme, light);
export const darkTheme = paperTheme(MD3DarkTheme, dark);
export type AppTheme = typeof lightTheme;

// ---------------------------------------------------------------- semantic helpers
export type Level = 'ok' | 'warn' | 'alert' | 'idle';

export function levelOf(v?: string | null): Level {
  if (!v) return 'idle';
  if (/OVERCOOLED/i.test(v)) return 'warn';
  if (/HAZARD|POOR_AIR|EMERGENCY|critical|alert|WASTE/i.test(v)) return 'alert';
  if (/WARNING|UNCOMFORTABLE|OVERCOOLED|ELEVATED|SAFE_HOLD|high|medium|warn/i.test(v)) return 'warn';
  if (/NORMAL|COMFORTABLE|COMPLIANT|IDLE|Good|low|ok/i.test(v)) return 'ok';
  return 'idle';
}

export function levelColors(p: Palette, l: Level) {
  switch (l) {
    case 'alert':
      return { fg: p.danger, bg: p.dangerSoft };
    case 'warn':
      return { fg: p.amber, bg: p.amberSoft };
    case 'ok':
      return { fg: p.ok, bg: p.okSoft };
    default:
      return { fg: p.inkSoft, bg: p.sunken };
  }
}

/** "UNCOMFORTABLE_HOT_HUMID" -> "Uncomfortable hot humid" (sentence case) */
export function pretty(v?: string | null): string {
  if (!v) return '—';
  const s = v.replace(/_/g, ' ').toLowerCase();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const COMFORT_LABEL: Record<string, string> = {
  COMFORTABLE: 'Comfortable',
  OVERCOOLED_ENERGY_WASTE: 'Over-cooled',
  UNCOMFORTABLE_HOT_HUMID: 'Hot and humid',
  UNCOMFORTABLE_HOT: 'Too warm',
  UNCOMFORTABLE_COLD: 'Too cold',
  UNCOMFORTABLE_HUMID: 'Too humid',
  UNCOMFORTABLE_DRY: 'Too dry',
};

export const STATE_LABEL: Record<string, string> = {
  IDLE: 'Ready',
  MANUAL: 'Manual drive',
  AUTONOMOUS_PATROL: 'On a mission',
  EMERGENCY_STOP: 'Emergency stop',
  SAFE_HOLD: 'Safe hold',
};

export const ZONE_LABEL = (z?: string | null) => (z ? z.replace(/_/g, ' ').replace(/([a-z])([A-Z][a-z])/g, '$1 $2') : 'Corridor');

/** Short label for tight spaces (map): "Lecture Hall B" -> "Hall B". */
export const ZONE_SHORT = (z?: string | null) => {
  const words = ZONE_LABEL(z).split(' ');
  return words.length > 2 ? words.slice(-2).join(' ') : words.join(' ');
};

export function timeAgo(ts?: number | null): string {
  if (!ts) return 'never';
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  const d = Math.floor(s / 86400);
  return d === 1 ? 'yesterday' : `${d} days ago`;
}

// legacy helper kept for older components
export function verdictColor(v?: string | null): string {
  return levelColors(light, levelOf(v)).fg;
}
