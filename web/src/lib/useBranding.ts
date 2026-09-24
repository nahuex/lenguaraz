// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from 'react';
import { DEFAULT_BRANDING, fetchBranding, type Branding } from './api';

/**
 * Load `GET /api/branding` once and expose the event identity. Falls back to the neutral
 * Lenguaraz theme when the backend is unreachable, so pages never render empty headers.
 * The brand color is published as the `--brand` CSS variable on the document root; theme
 * tokens for contrast stay untouched (accessibility first).
 */
export function useBranding(): Branding {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    fetchBranding(controller.signal)
      .then((result) => {
        if (!cancelled) setBranding(result);
      })
      .catch(() => {
        /* keep defaults */
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty('--brand', branding.primary_color);
  }, [branding.primary_color]);

  return branding;
}
