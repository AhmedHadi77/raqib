import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import React from 'react';
import { Pressable, StyleSheet, Text, View, type ColorValue } from 'react-native';

import { usePalette } from '@/hooks';
import { useAppSelector } from '@/store';
import { BRAND, fonts } from '@/theme';

type IconName = keyof typeof MaterialCommunityIcons.glyphMap;

/** Raised centre button for the Assistant (the product's main way in). */
function AssistantTabButton(props: any) {
  const p = usePalette();
  const busy = useAppSelector((s) => s.chat.busy);
  const focused = props.accessibilityState?.selected;
  return (
    <Pressable onPress={props.onPress} onLongPress={props.onLongPress} accessibilityRole="button"
      accessibilityLabel="Assistant" accessibilityState={props.accessibilityState} style={styles.centerWrap}>
      <View style={[styles.center, { backgroundColor: BRAND.navy, borderColor: p.paper }]}>
        <MaterialCommunityIcons name={busy ? 'dots-horizontal' : 'microphone'} size={26} color={BRAND.cyan} />
      </View>
      <Text style={{ fontFamily: fonts.bodyMedium, fontSize: 11.5, color: focused ? p.primary : p.inkSoft, marginTop: 2 }}>
        Assistant
      </Text>
    </Pressable>
  );
}

export default function TabLayout() {
  const p = usePalette();
  const faults = useAppSelector((s) => s.robot.telemetry?.faults?.length ?? 0);
  const icon = (name: IconName) => ({ color, size }: { color: ColorValue; size: number }) => (
    <MaterialCommunityIcons name={name} size={size} color={color as string} />
  );
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: p.primary,
        tabBarInactiveTintColor: p.inkSoft,
        tabBarStyle: { backgroundColor: p.surface, borderTopColor: p.line, height: 64, paddingTop: 6 },
        tabBarLabelStyle: { fontFamily: fonts.bodyMedium, fontSize: 11.5 },
        headerStyle: { backgroundColor: p.paper },
        headerShadowVisible: false,
        headerTintColor: p.ink,
        headerTitleStyle: { fontFamily: fonts.heading, fontSize: 17 },
        sceneStyle: { backgroundColor: p.paper },
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Home', headerShown: false, tabBarIcon: icon('home-variant-outline') }} />
      <Tabs.Screen name="drive" options={{ title: 'Drive', headerShown: false, tabBarIcon: icon('gamepad-round-outline') }} />
      <Tabs.Screen name="chat" options={{ title: 'Assistant', headerShown: false, tabBarButton: (props) => <AssistantTabButton {...props} /> }} />
      <Tabs.Screen name="reports" options={{ title: 'Reports', tabBarIcon: icon('clipboard-text-outline') }} />
      <Tabs.Screen name="more" options={{
        title: 'More', headerShown: false, tabBarIcon: icon('dots-grid'),
        tabBarBadge: faults ? faults : undefined, tabBarBadgeStyle: { backgroundColor: p.danger, fontSize: 11 },
      }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  centerWrap: { flex: 1, alignItems: 'center', justifyContent: 'flex-start' },
  center: {
    width: 56, height: 56, borderRadius: 28, marginTop: -22, alignItems: 'center', justifyContent: 'center', borderWidth: 4,
    shadowColor: '#0D1530', shadowOpacity: 0.25, shadowRadius: 8, shadowOffset: { width: 0, height: 4 }, elevation: 6,
  },
});
