// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ChoiceGroup } from './ChoiceGroup';

const OPTIONS = [
  { value: 'a', label: 'A', name: 'Alpha' },
  { value: 'b', label: 'B', name: 'Bravo' },
  { value: 'c', label: 'C' },
] as const;

describe('ChoiceGroup', () => {
  it('is a radiogroup named by its label, with one radio per option', () => {
    render(<ChoiceGroup label="Letter" options={OPTIONS} value="b" onChange={() => undefined} />);
    const group = screen.getByRole('radiogroup', { name: 'Letter' });
    expect(group).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(3);
    // The accessible name is the long form when given, the visible text otherwise.
    expect(screen.getByRole('radio', { name: 'Alpha' })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: 'Bravo' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'C' })).not.toBeChecked();
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('reports a new choice and ignores re-pressing the current one', () => {
    const onChange = vi.fn();
    render(<ChoiceGroup label="Letter" options={OPTIONS} value="b" onChange={onChange} />);

    fireEvent.click(screen.getByRole('radio', { name: 'Alpha' }));
    expect(onChange).toHaveBeenCalledWith('a');

    onChange.mockClear();
    fireEvent.click(screen.getByRole('radio', { name: 'Bravo' }));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole('radio', { name: 'Bravo' })).toBeChecked();
  });
});
