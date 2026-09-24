// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { CaptionView } from './CaptionView';
import type { Caption } from '../lib/captions';

function caption(seq: number, text: string, original?: string): Caption {
  return {
    stage_id: 'main',
    seq,
    lang: 'es',
    source_lang: 'en',
    is_final: true,
    text,
    original,
    t_audio_ms: seq * 1000,
    latency_ms: 800,
  };
}

describe('CaptionView', () => {
  it('exposes a polite, non-atomic live region', () => {
    render(<CaptionView finals={[]} interim={null} lines={3} showOriginal={false} />);
    const region = screen.getByRole('region', { name: 'Captions' });
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'false');
  });

  it('shows only the last N finals with the newest at the bottom, then the interim', () => {
    const finals = [caption(1, 'one'), caption(2, 'two'), caption(3, 'three'), caption(4, 'four')];
    const interim = { ...caption(5, 'fi'), is_final: false };
    render(<CaptionView finals={finals} interim={interim} lines={2} showOriginal={false} />);

    const region = screen.getByRole('region', { name: 'Captions' });
    const lines = within(region).getAllByText(/^(one|two|three|four)$/);
    expect(lines.map((el) => el.textContent)).toEqual(['three', 'four']);

    const interimLine = screen.getByText('fi');
    expect(interimLine.closest('[data-interim]')).not.toBeNull();
    expect(region.contains(interimLine)).toBe(false);
  });

  it('shows the original under a translated line only when enabled and different', () => {
    const finals = [caption(1, 'hola', 'hello'), caption(2, 'same', 'same')];
    const { rerender } = render(
      <CaptionView finals={finals} interim={null} lines={3} showOriginal={false} />,
    );
    expect(screen.queryByText('hello')).toBeNull();

    rerender(<CaptionView finals={finals} interim={null} lines={3} showOriginal={true} />);
    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.getAllByText('same')).toHaveLength(1);
  });
});
