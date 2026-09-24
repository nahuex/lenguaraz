// SPDX-License-Identifier: Apache-2.0
import { useId } from 'react';
import { FONT_SIZES, setPref, usePrefs } from '../lib/prefs';

const FONT_SIZE_TITLES: Record<string, string> = {
  S: 'Small',
  M: 'Medium',
  L: 'Large',
  XL: 'Extra large',
};

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}

function Toggle({ label, checked, onChange }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
        checked ? 'border-accent bg-accent text-accent-ink' : 'border-line bg-surface-raised text-ink'
      }`}
    >
      {label}
    </button>
  );
}

/**
 * Display settings: caption font size, high contrast, dark/light theme and
 * "show original". Values persist in localStorage (see src/lib/prefs.ts).
 */
export function A11yControls() {
  const prefs = usePrefs();
  const groupId = useId();

  return (
    <div role="group" aria-label="Display settings" className="flex flex-wrap items-end gap-4">
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend className="mb-1 w-full text-sm font-semibold text-ink-muted">Caption font size</legend>
        {FONT_SIZES.map((size) => {
          const checked = prefs.fontSize === size;
          return (
            <label
              key={size}
              title={FONT_SIZE_TITLES[size]}
              className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${
                checked ? 'border-accent bg-accent text-accent-ink' : 'border-line bg-surface-raised text-ink'
              }`}
            >
              <input
                type="radio"
                name={`font-size-${groupId}`}
                value={size}
                checked={checked}
                onChange={() => setPref('fontSize', size)}
                className="sr-only"
              />
              {size}
            </label>
          );
        })}
      </fieldset>
      <div className="flex flex-wrap items-center gap-2">
        <Toggle
          label="High contrast"
          checked={prefs.highContrast}
          onChange={(next) => setPref('highContrast', next)}
        />
        <Toggle
          label="Dark theme"
          checked={prefs.theme === 'dark'}
          onChange={(next) => setPref('theme', next ? 'dark' : 'light')}
        />
        <Toggle
          label="Show original"
          checked={prefs.showOriginal}
          onChange={(next) => setPref('showOriginal', next)}
        />
      </div>
    </div>
  );
}
