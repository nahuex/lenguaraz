// SPDX-License-Identifier: Apache-2.0
import { useId, type ReactNode } from 'react';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

export interface ChoiceOption<T extends string> {
  value: T;
  /** Visible content, usually a short form ("S", "3"). */
  label: ReactNode;
  /** Accessible name when the visible label is an abbreviation ("Small", "3 lines"). */
  name?: string;
}

interface ChoiceGroupProps<T extends string> {
  /** Visible group label; also the group's accessible name. */
  label: string;
  options: readonly ChoiceOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/**
 * Labelled single-choice segmented control on the ToggleGroup primitive. Radix renders it
 * as a radiogroup of radios with roving focus (arrow keys move, Space/Enter select); the
 * selected item is painted with the primary colour so the choice reads at a glance. Exactly
 * one option is always selected: re-pressing the current one is ignored.
 */
export function ChoiceGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: ChoiceGroupProps<T>) {
  const labelId = useId();

  const handleChange = (next: string): void => {
    const option = options.find((candidate) => candidate.value === next);
    if (option) onChange(option.value);
  };

  return (
    <div className="flex flex-col gap-2">
      <span id={labelId} className="text-sm font-semibold text-muted-foreground">
        {label}
      </span>
      <ToggleGroup
        type="single"
        variant="outline"
        value={value}
        onValueChange={handleChange}
        aria-labelledby={labelId}
      >
        {options.map((option) => (
          <ToggleGroupItem
            key={option.value}
            value={option.value}
            aria-label={option.name}
            className="min-w-10 data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            {option.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
