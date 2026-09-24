// SPDX-License-Identifier: Apache-2.0
import { useSyncExternalStore } from 'react';

/**
 * Viewer display preferences (font size, contrast, theme, show original).
 * A tiny external store so every component sees the same values; persisted
 * in localStorage and mirrored as data attributes on <html> for the CSS.
 */

export type FontSize = 'S' | 'M' | 'L' | 'XL';
export type Theme = 'dark' | 'light';

export interface Prefs {
  fontSize: FontSize;
  highContrast: boolean;
  theme: Theme;
  showOriginal: boolean;
}

export const FONT_SIZES: readonly FontSize[] = ['S', 'M', 'L', 'XL'];

export const STORAGE_KEYS = {
  fontSize: 'lenguaraz.fontSize',
  highContrast: 'lenguaraz.highContrast',
  theme: 'lenguaraz.theme',
  showOriginal: 'lenguaraz.showOriginal',
} as const;

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage may be unavailable (private mode, blocked, quota); ignore.
  }
}

function systemTheme(): Theme {
  try {
    if (typeof window.matchMedia === 'function') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
  } catch {
    // Fall through to the default.
  }
  return 'dark';
}

function isFontSize(value: string | null): value is FontSize {
  return value !== null && (FONT_SIZES as readonly string[]).includes(value);
}

function loadPrefs(): Prefs {
  const fontSize = readStorage(STORAGE_KEYS.fontSize);
  const theme = readStorage(STORAGE_KEYS.theme);
  return {
    fontSize: isFontSize(fontSize) ? fontSize : 'M',
    highContrast: readStorage(STORAGE_KEYS.highContrast) === 'true',
    theme: theme === 'dark' || theme === 'light' ? theme : systemTheme(),
    showOriginal: readStorage(STORAGE_KEYS.showOriginal) === 'true',
  };
}

let prefs: Prefs = loadPrefs();
const listeners = new Set<() => void>();

/** Mirror the preferences onto <html> so the stylesheet can react. */
export function applyPrefsToDocument(current: Prefs = prefs): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.dataset.theme = current.theme;
  root.dataset.contrast = current.highContrast ? 'high' : 'normal';
  root.dataset.fontSize = current.fontSize;
}

export function getPrefs(): Prefs {
  return prefs;
}

export function setPref<K extends keyof Prefs>(key: K, value: Prefs[K]): void {
  if (prefs[key] === value) return;
  prefs = { ...prefs, [key]: value };
  writeStorage(STORAGE_KEYS[key], String(value));
  applyPrefsToDocument(prefs);
  for (const listener of listeners) listener();
}

export function subscribePrefs(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Re-read localStorage and re-apply; used at startup and by tests. */
export function reloadPrefs(): Prefs {
  prefs = loadPrefs();
  applyPrefsToDocument(prefs);
  for (const listener of listeners) listener();
  return prefs;
}

export function usePrefs(): Prefs {
  return useSyncExternalStore(subscribePrefs, getPrefs, getPrefs);
}
