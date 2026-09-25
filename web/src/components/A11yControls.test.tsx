// SPDX-License-Identifier: Apache-2.0
import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { A11yControls } from './A11yControls';
import { reloadPrefs } from '../lib/prefs';

describe('A11yControls', () => {
  beforeEach(() => {
    window.localStorage.clear();
    reloadPrefs();
  });

  it('persists font size L and applies it as a data attribute', () => {
    render(<A11yControls />);
    fireEvent.click(screen.getByRole('radio', { name: 'Large' }));

    expect(window.localStorage.getItem('lenguaraz.fontSize')).toBe('L');
    expect(document.documentElement.dataset.fontSize).toBe('L');
    expect(screen.getByRole('radio', { name: 'Large' })).toBeChecked();
  });

  it('restores the persisted font size on load', () => {
    window.localStorage.setItem('lenguaraz.fontSize', 'XL');
    reloadPrefs();
    render(<A11yControls />);
    expect(screen.getByRole('radio', { name: 'Extra large' })).toBeChecked();
    // The visible label stays the short form; the accessible name is the full word.
    expect(screen.getByText('XL')).toBeInTheDocument();
  });

  it('toggles high contrast, theme and show-original with persistence', () => {
    render(<A11yControls />);

    fireEvent.click(screen.getByRole('switch', { name: 'High contrast' }));
    expect(window.localStorage.getItem('lenguaraz.highContrast')).toBe('true');
    expect(document.documentElement.dataset.contrast).toBe('high');

    const dark = screen.getByRole('switch', { name: 'Dark theme' });
    const wasDark = dark.getAttribute('aria-checked') === 'true';
    fireEvent.click(dark);
    expect(window.localStorage.getItem('lenguaraz.theme')).toBe(wasDark ? 'light' : 'dark');
    expect(document.documentElement.dataset.theme).toBe(wasDark ? 'light' : 'dark');

    fireEvent.click(screen.getByRole('switch', { name: 'Show original' }));
    expect(window.localStorage.getItem('lenguaraz.showOriginal')).toBe('true');
  });
});
