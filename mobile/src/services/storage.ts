import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// SecureStore (Keychain / Keystore) on phones, localStorage on web.
export async function save(key: string, value: string | null): Promise<void> {
  try {
    if (Platform.OS === 'web') {
      if (value === null) globalThis.localStorage?.removeItem(key);
      else globalThis.localStorage?.setItem(key, value);
      return;
    }
    if (value === null) await SecureStore.deleteItemAsync(key);
    else await SecureStore.setItemAsync(key, value);
  } catch {
    // storage unavailable - the app still works for this session
  }
}

export async function load(key: string): Promise<string | null> {
  try {
    if (Platform.OS === 'web') return globalThis.localStorage?.getItem(key) ?? null;
    return await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
}
