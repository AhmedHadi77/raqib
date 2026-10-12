// Scan the QR code shown on http://<pc>:8000/connect to fill in the server address.
import { CameraView, useCameraPermissions } from 'expo-camera';
import { router } from 'expo-router';
import React, { useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Body, H1 } from '@/components/ui';
import { usePalette } from '@/hooks';

export default function Scan() {
  const p = usePalette();
  const [perm, requestPerm] = useCameraPermissions();
  const done = useRef(false);

  if (!perm) return <View style={{ flex: 1, backgroundColor: p.paper }} />;
  if (!perm.granted)
    return (
      <SafeAreaView style={[styles.center, { backgroundColor: p.paper }]}>
        <H1 style={{ fontSize: 24, textAlign: 'center' }}>Camera needed</H1>
        <Body soft style={{ textAlign: 'center', marginVertical: 12 }}>
          The app uses the camera only to read the pairing QR code.
        </Body>
        <Button mode="contained" onPress={requestPerm}>Allow camera</Button>
        <Button onPress={() => router.back()} style={{ marginTop: 6 }}>Type the address instead</Button>
      </SafeAreaView>
    );

  return (
    <View style={{ flex: 1, backgroundColor: '#000' }}>
      <CameraView
        style={StyleSheet.absoluteFill}
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={({ data }) => {
          if (done.current || !/^https?:\/\//.test(data)) return;
          done.current = true;
          router.replace({ pathname: '/login', params: { server: data.replace(/\/+$/, '') } });
        }}
      />
      <SafeAreaView style={styles.overlay} pointerEvents="box-none">
        <View style={styles.frame} />
        <Body style={{ color: '#fff', textAlign: 'center', marginTop: 18 }}>
          Point at the QR code on your PC screen (http://your-pc:8000/connect)
        </Body>
        <Button mode="contained-tonal" onPress={() => router.back()} style={{ marginTop: 18 }}>Cancel</Button>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  overlay: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  frame: { width: 240, height: 240, borderRadius: 24, borderWidth: 3, borderColor: '#ffffffcc' },
});
