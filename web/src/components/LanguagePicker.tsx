// SPDX-License-Identifier: Apache-2.0
import { useId } from 'react';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import type { LanguageOption } from '../lib/lang';

interface LanguagePickerProps {
  options: LanguageOption[];
  value: string;
  onChange: (code: string) => void;
}

/** Radio group of caption languages; the original language is marked. */
export function LanguagePicker({ options, value, onChange }: LanguagePickerProps) {
  const id = useId();
  const labelId = `${id}-label`;

  return (
    <div className="flex flex-col gap-2">
      <span id={labelId} className="text-sm font-semibold text-muted-foreground">
        Caption language
      </span>
      <RadioGroup
        value={value}
        onValueChange={onChange}
        aria-labelledby={labelId}
        className="flex flex-wrap items-center gap-x-6 gap-y-3"
      >
        {options.map((option) => {
          const itemId = `${id}-${option.code}`;
          return (
            <div key={option.code} className="flex items-center gap-2">
              <RadioGroupItem id={itemId} value={option.code} />
              <Label htmlFor={itemId} className="cursor-pointer text-base">
                {option.original ? `${option.label} (original)` : option.label}
              </Label>
            </div>
          );
        })}
      </RadioGroup>
    </div>
  );
}
