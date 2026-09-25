// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { LanguagePicker } from './LanguagePicker';
import { buildLanguageOptions } from '../lib/lang';

describe('LanguagePicker', () => {
  const options = buildLanguageOptions({ source_lang: ['en-US'], targets: ['es', 'en'] });

  it('renders a named radiogroup with one radio per language and marks the original', () => {
    render(<LanguagePicker options={options} value="en" onChange={() => undefined} />);
    expect(screen.getByRole('radiogroup', { name: 'Caption language' })).toBeInTheDocument();
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
    expect(screen.getByRole('radio', { name: 'English (original)' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Spanish' })).not.toBeChecked();
  });

  it('calls onChange with the short code', () => {
    const onChange = vi.fn();
    render(<LanguagePicker options={options} value="en" onChange={onChange} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Spanish' }));
    expect(onChange).toHaveBeenCalledWith('es');
  });

  it('selects a language from its label too', () => {
    const onChange = vi.fn();
    render(<LanguagePicker options={options} value="en" onChange={onChange} />);
    fireEvent.click(screen.getByText('Spanish'));
    expect(onChange).toHaveBeenCalledWith('es');
  });
});
