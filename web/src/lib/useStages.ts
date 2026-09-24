// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from 'react';
import { fetchStages, type Stage } from './api';

export interface StagesPoll {
  /** `null` until the first response arrives. */
  stages: Stage[] | null;
  /** Last fetch error message, or `null` when the last fetch succeeded. */
  error: string | null;
}

/** Poll `GET /api/stages` on mount and every `intervalMs`. */
export function useStages(intervalMs = 5000): StagesPoll {
  const [stages, setStages] = useState<Stage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const load = async (): Promise<void> => {
      try {
        const result = await fetchStages(controller.signal);
        if (cancelled) return;
        setStages(result);
        setError(null);
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : 'backend unreachable');
      }
    };

    void load();
    const timer = setInterval(() => {
      void load();
    }, intervalMs);

    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [intervalMs]);

  return { stages, error };
}
