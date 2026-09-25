// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Overlay, overlayFontSize, parseOverlayOptions } from './Overlay';
import type { Stage } from '../lib/api';
import type { CaptionEvent, WebSocketLike } from '../lib/captions';

/** In-memory WebSocket stand-in, driven from the test (same approach as captions.test.ts). */
class FakeSocket implements WebSocketLike {
  static instances: FakeSocket[] = [];

  readyState = 0;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  send(): void {
    // Pings are irrelevant here.
  }

  close(): void {
    this.readyState = 3;
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  message(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as unknown as MessageEvent);
  }

  serverClose(code: number, reason = ''): void {
    this.readyState = 3;
    this.onclose?.({ code, reason } as unknown as CloseEvent);
  }
}

const STAGE: Stage = {
  id: 'main',
  name: 'Main Stage',
  state: 'LIVE',
  detail: null,
  source_lang: ['en-US'],
  targets: ['es'],
  listeners: 3,
  dry_run: true,
};

function caption(seq: number, isFinal: boolean, text: string): CaptionEvent {
  return {
    type: 'caption',
    stage_id: 'main',
    seq,
    lang: 'es',
    source_lang: 'en',
    is_final: isFinal,
    text,
    t_audio_ms: seq * 1000,
    latency_ms: 700,
  };
}

function renderOverlay(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/overlay/:stage" element={<Overlay />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('parseOverlayOptions', () => {
  it('applies defaults and clamps lines to 1-5', () => {
    expect(parseOverlayOptions(new URLSearchParams(''))).toEqual({
      lines: 2,
      size: 'l',
      align: 'bottom',
      bg: 'band',
    });
    expect(parseOverlayOptions(new URLSearchParams('lines=9&size=XL&align=top&bg=none'))).toEqual({
      lines: 5,
      size: 'xl',
      align: 'top',
      bg: 'none',
    });
    expect(parseOverlayOptions(new URLSearchParams('lines=0&size=huge')).lines).toBe(1);
  });

  it('maps sizes to px capped values that scale with the viewport', () => {
    expect(overlayFontSize('s')).toContain('28px');
    expect(overlayFontSize('l')).toMatch(/^min\(56px, [\d.]+vw\)$/);
  });
});

describe('Overlay', () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify([STAGE]), { status: 200 })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows only the last 2 finals plus the interim line, transparent and without chrome', async () => {
    renderOverlay('/overlay/main?lines=2&lang=es');

    expect(document.documentElement.dataset.overlay).toBe('true');
    const socket = FakeSocket.instances[0];
    expect(socket?.url).toMatch(/\/ws\/main\?lang=es$/);

    act(() => {
      socket?.open();
      socket?.message(caption(1, true, 'first line'));
      socket?.message(caption(2, true, 'second line'));
      socket?.message(caption(3, true, 'third line'));
      socket?.message(caption(4, false, 'typing'));
    });

    const region = screen.getByRole('region', { name: 'Captions' });
    const finals = within(region).getAllByText(/line$/);
    expect(finals.map((el) => el.textContent)).toEqual(['second line', 'third line']);
    expect(screen.queryByText('first line')).toBeNull();

    const interim = screen.getByText('typing');
    expect(interim).toHaveAttribute('data-interim', 'true');
    expect(region.contains(interim)).toBe(true);

    // No page chrome: no headings, links, buttons or form controls.
    expect(screen.queryByRole('heading')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();

    // The dry-run tag appears once /api/stages reports dry_run.
    expect(await screen.findByText('Dry run · simulated captions, no API key')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows a one-line error on a fatal close code', () => {
    renderOverlay('/overlay/ghost?lang=es');
    act(() => {
      FakeSocket.instances[0]?.serverClose(4404, 'no such stage');
    });
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent("Lenguaraz overlay: stage 'ghost' was not found.");
    // The raw close reason is never echoed on the stream.
    expect(alert).not.toHaveTextContent('no such stage');
  });

  it('cleans the overlay attribute up on unmount', () => {
    const { unmount } = renderOverlay('/overlay/main?lang=es');
    expect(document.documentElement.dataset.overlay).toBe('true');
    unmount();
    expect(document.documentElement.dataset.overlay).toBeUndefined();
  });
});
