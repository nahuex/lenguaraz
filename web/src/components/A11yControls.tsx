// SPDX-License-Identifier: Apache-2.0
import { useId } from 'react';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { ChoiceGroup, type ChoiceOption } from './ChoiceGroup';
import { FONT_SIZES, setPref, usePrefs, type FontSize } from '../lib/prefs';

const FONT_SIZE_TITLES: Record<FontSize, string> = {
  S: 'Small',
  M: 'Medium',
  L: 'Large',
  XL: 'Extra large',
};

/** Visible S/M/L/XL; the accessible name is the full word. */
const FONT_SIZE_CHOICES: readonly ChoiceOption<FontSize>[] = FONT_SIZES.map((size) => ({
  value: size,
  label: size,
  name: FONT_SIZE_TITLES[size],
}));

interface PrefSwitchProps {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}

function PrefSwitch({ label, checked, onChange }: PrefSwitchProps) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
      <Label htmlFor={id} className="cursor-pointer">
        {label}
      </Label>
    </div>
  );
}

/**
 * Display settings: caption font size, high contrast, dark/light theme and
 * "show original". Values persist in localStorage (see src/lib/prefs.ts).
 */
export function A11yControls() {
  const prefs = usePrefs();

  return (
    <div
      role="group"
      aria-label="Display settings"
      className="flex flex-wrap items-end gap-x-6 gap-y-4"
    >
      <ChoiceGroup
        label="Font size"
        options={FONT_SIZE_CHOICES}
        value={prefs.fontSize}
        onChange={(size) => setPref('fontSize', size)}
      />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 pb-1">
        <PrefSwitch
          label="High contrast"
          checked={prefs.highContrast}
          onChange={(next) => setPref('highContrast', next)}
        />
        <PrefSwitch
          label="Dark theme"
          checked={prefs.theme === 'dark'}
          onChange={(next) => setPref('theme', next ? 'dark' : 'light')}
        />
        <PrefSwitch
          label="Show original"
          checked={prefs.showOriginal}
          onChange={(next) => setPref('showOriginal', next)}
        />
      </div>
    </div>
  );
}
