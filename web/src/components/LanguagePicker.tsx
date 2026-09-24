// SPDX-License-Identifier: Apache-2.0
import { useId } from 'react';
import type { LanguageOption } from '../lib/lang';

interface LanguagePickerProps {
  options: LanguageOption[];
  value: string;
  onChange: (code: string) => void;
}

/** Radio group of caption languages; the original language is marked. */
export function LanguagePicker({ options, value, onChange }: LanguagePickerProps) {
  const groupId = useId();
  const name = `lang-${groupId}`;

  return (
    <fieldset className="flex flex-wrap items-center gap-2">
      <legend className="mb-1 w-full text-sm font-semibold text-ink-muted">Caption language</legend>
      {options.map((option) => {
        const checked = option.code === value;
        return (
          <label
            key={option.code}
            className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${
              checked
                ? 'border-accent bg-accent text-accent-ink'
                : 'border-line bg-surface-raised text-ink'
            }`}
          >
            <input
              type="radio"
              name={name}
              value={option.code}
              checked={checked}
              onChange={() => onChange(option.code)}
              className="sr-only"
            />
            {option.original ? `${option.label} (original)` : option.label}
          </label>
        );
      })}
    </fieldset>
  );
}
