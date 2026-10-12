import { Archivo_600SemiBold, Archivo_700Bold, Archivo_800ExtraBold } from '@expo-google-fonts/archivo';
import { PublicSans_400Regular, PublicSans_500Medium, PublicSans_600SemiBold } from '@expo-google-fonts/public-sans';
import Constants from 'expo-constants';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { Platform, useColorScheme } from 'react-native';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Provider } from 'react-redux';

import AlertBanner from '@/components/AlertBanner';
import { requestAlertPermission } from '@/services/alerts';
import { api } from '@/services/api';
import { realtime } from '@/services/realtime';
import { load, save } from '@/services/storage';
import { PERSISTED, robotActions, sessionActions, store, useAppDispatch, useAppSelector } from '@/store';
import { usePalette } from '@/hooks';
import { darkTheme, fonts, lightTheme } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(() => {});

function Bootstrap({ fontsReady }: { fontsReady: boolean }) {
  const dispatch = useAppDispatch();
  const p = usePalette();
  const session = useAppSelector((s) => s.session);
  const { hydrated, token, serverUrl, robotId, notifications } = session;

  // 1. restore saved settings + session
  useEffect(() => {
    (async () => {
      const extra = (Constants.expoConfig?.extra ?? {}) as Record<string, string>;
      const saved = await load('session');
      const parsed = saved ? JSON.parse(saved) : {};
      // web build served by the backend itself -> talk to the same origin by default
      const webOrigin =
        Platform.OS === 'web' && typeof window !== 'undefined' && /^https?:/.test(window.location.origin)
          ? window.location.origin
          : null;
      dispatch(
        sessionActions.hydrate({
          ...parsed,
          serverUrl: parsed.serverUrl ?? webOrigin ?? extra.defaultServerUrl ?? 'http://192.168.1.100:8000',
          robotId: parsed.robotId ?? extra.defaultRobotId ?? 'robot01',
        }),
      );
    })();
  }, [dispatch]);

  // 2. persist on change
  useEffect(() => {
    if (!hydrated) return;
    const out: Record<string, unknown> = {};
    for (const k of PERSISTED) out[k] = (session as any)[k];
    save('session', JSON.stringify(out));
  }, [hydrated, session]);

  // 3. live connection, robot info and alert permission while signed in
  useEffect(() => {
    if (hydrated && token) {
      realtime.restart();
      api.robot(robotId).then((r) => r.info && dispatch(robotActions.info(r.info))).catch(() => {});
      // plug and play: if this server has no robot with our id but has another one, use that one
      api.health().then((h) => {
        const ids = Object.keys(h.robots ?? {});
        if (!ids.length || ids.includes(robotId)) return;
        const pick = ids.find((id) => (h.robots as any)[id]?.online) ?? ids[0];
        dispatch(sessionActions.setServer({ serverUrl, robotId: pick }));
      }).catch(() => {});
      if (notifications) requestAlertPermission();
    } else realtime.stop();
  }, [hydrated, token, serverUrl, robotId, notifications, dispatch]);

  const ready = hydrated && fontsReady;
  useEffect(() => {
    if (ready) SplashScreen.hideAsync().catch(() => {});
  }, [ready]);
  if (!ready) return null;

  const stackHeader = {
    headerShown: true,
    headerShadowVisible: false,
    headerBackTitle: 'Back',
    headerTitleStyle: { fontFamily: fonts.heading, fontSize: 17 },
    headerStyle: { backgroundColor: p.paper },
    headerTintColor: p.ink,
    contentStyle: { backgroundColor: p.paper },
  } as const;

  return (
    <>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Protected guard={!!token}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="report/[id]" options={{ ...stackHeader, title: 'Inspection report' }} />
          <Stack.Screen name="insights" options={{ ...stackHeader, title: 'Insights' }} />
          <Stack.Screen name="schedules" options={{ ...stackHeader, title: 'Scheduled patrols' }} />
          <Stack.Screen name="health" options={{ ...stackHeader, title: 'Robot health' }} />
          <Stack.Screen name="users" options={{ ...stackHeader, title: 'Users' }} />
          <Stack.Screen name="settings" options={{ ...stackHeader, title: 'Settings' }} />
          <Stack.Screen name="monitor" options={{ ...stackHeader, title: 'Exam monitor' }} />
          <Stack.Screen name="ai" options={{ ...stackHeader, title: 'AI settings' }} />
        </Stack.Protected>
        <Stack.Protected guard={!token}>
          <Stack.Screen name="login" />
          <Stack.Screen name="scan" options={{ presentation: 'modal' }} />
        </Stack.Protected>
      </Stack>
      {token ? <AlertBanner /> : null}
    </>
  );
}

function Themed() {
  const scheme = useColorScheme();
  const mode = useAppSelector((s) => s.session.themeMode);
  const [fontsLoaded, fontError] = useFonts({
    Archivo_600SemiBold,
    Archivo_700Bold,
    Archivo_800ExtraBold,
    PublicSans_400Regular,
    PublicSans_500Medium,
    PublicSans_600SemiBold,
  });
  const isDark = mode === 'dark' || (mode === 'system' && scheme === 'dark');
  const theme = isDark ? darkTheme : lightTheme;
  const p = theme.palette;
  return (
    <PaperProvider theme={theme}>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <ThemeNav paper={p.paper} ink={p.ink}>
        <Bootstrap fontsReady={fontsLoaded || !!fontError} />
      </ThemeNav>
    </PaperProvider>
  );
}

/** Page background follows the theme on web too (no white flash around the app). */
function ThemeNav({ children, paper }: { children: React.ReactNode; paper: string; ink?: string }) {
  useEffect(() => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') document.body.style.backgroundColor = paper;
  }, [paper]);
  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <Provider store={store}>
      <SafeAreaProvider>
        <Themed />
      </SafeAreaProvider>
    </Provider>
  );
}
