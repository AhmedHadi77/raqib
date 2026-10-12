import { useCallback, useEffect, useRef, useState } from 'react';
import { useTheme } from 'react-native-paper';

import type { AppTheme, Palette } from '@/theme';

export function usePalette(): Palette {
  return (useTheme() as unknown as AppTheme).palette;
}

/** Poll an async loader every `ms` while mounted. */
export function usePolling<T>(load: () => Promise<T>, ms: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  const run = useCallback(async () => {
    try {
      const d = await load();
      if (alive.current) {
        setData(d);
        setError(null);
      }
    } catch (e: any) {
      if (alive.current) setError(e?.message ?? String(e));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    alive.current = true;
    run();
    const t = setInterval(run, ms);
    return () => {
      alive.current = false;
      clearInterval(t);
    };
  }, [run, ms]);
  return { data, error, refresh: run };
}
