// SPDX-License-Identifier: Apache-2.0
import { useEffect, useState } from 'react';
import { DEFAULT_BRANDING, fetchBranding, type Branding } from './api';
import { usePrefs } from './prefs';

/** Design-system tokens the brand colour overrides at runtime (inline on <html>). */
const BRAND_TOKENS = ['--primary', '--primary-foreground', '--ring'] as const;

/**
 * Black or white, whichever contrasts more with a `#RRGGBB` colour (WCAG 2.1 relative
 * luminance). Returns null for anything that is not a 6-digit hex colour.
 */
export function readableForeground(color: string): '#000000' | '#ffffff' | null {
  const match = /^#([0-9a-f]{6})$/i.exec(color.trim());
  if (!match) return null;
  const digits = match[1];
  const linear = (offset: number): number => {
    const c = parseInt(digits.slice(offset, offset + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const luminance = 0.2126 * linear(0) + 0.7152 * linear(2) + 0.0722 * linear(4);
  const againstBlack = (luminance + 0.05) / 0.05;
  const againstWhite = 1.05 / (luminance + 0.05);
  return againstBlack >= againstWhite ? '#000000' : '#ffffff';
}

/**
 * Load `GET /api/branding` once and expose the event identity. Falls back to the neutral
 * Lenguaraz theme when the backend is unreachable, so pages never render empty headers.
 * The brand colour is published as the `--brand` CSS variable on the document root and,
 * unless high contrast is active, also drives the design-system `--primary`, `--ring` and a
 * readable `--primary-foreground`. High contrast keeps the AAA pairs declared in index.css
 * (accessibility first), so the inline overrides are removed whenever the viewer switches
 * it on.
 */
export function useBranding(): Branding {
  const [branding, setBranding] = useState<Branding>(DEFAULT_BRANDING);
  const { highContrast } = usePrefs();

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
    const root = document.documentElement;
    const color = branding.primary_color;
    root.style.setProperty('--brand', color);
    // The data attribute is the source of truth (prefs.ts mirrors it before notifying);
    // `highContrast` in the dependency list re-runs this effect when the viewer toggles it.
    if (root.dataset.contrast === 'high') {
      for (const token of BRAND_TOKENS) root.style.removeProperty(token);
      return;
    }
    root.style.setProperty('--primary', color);
    root.style.setProperty('--ring', color);
    const foreground = readableForeground(color);
    if (foreground) root.style.setProperty('--primary-foreground', foreground);
    else root.style.removeProperty('--primary-foreground');
  }, [branding.primary_color, highContrast]);

  return branding;
}
