// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LiveCaptions } from './LiveCaptions';
import type { Stage } from '../lib/api';
import type { CaptionEvent, ServerEvent, WebSocketLike } from '../lib/captions';

/** In-memory WebSocket stand-in, driven from the test (same approach as Overlay.test.tsx). */
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

  message(payload: ServerEvent): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as unknown as MessageEvent);
  }
}

/** A degraded stage whose detail carries exception text that must never reach the audience. */
const STAGE: Stage = {
  id: 'main',
  name: 'Main Stage',
  state: 'DEGRADED',
  detail: 'RuntimeError: boom at engine.py:42',
  source_lang: ['en-US'],
  targets: ['es'],
  listeners: 3,
  dry_run: false,
};

function finalCaption(seq: number): CaptionEvent {
  return {
    type: 'caption',
    stage_id: 'main',
    seq,
    lang: 'es',
    source_lang: 'en',
    is_final: true,
    text: `line ${seq}`,
    t_audio_ms: seq * 1000,
    latency_ms: 800,
  };
}

function renderPage(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/live/:stage" element={<LiveCaptions />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('LiveCaptions', () => {
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

  it('shows audience copy per stage state and never the raw detail', async () => {
    renderPage('/live/main?lang=es');

    // Connection line: sentence case, no "Connection:" prefix.
    expect(screen.getByText('Connecting…')).toBeInTheDocument();

    expect(
      await screen.findByText('Captions are running with reduced quality.'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/RuntimeError|boom|engine\.py/)).toBeNull();

    const socket = FakeSocket.instances[0];
    act(() => {
      socket?.open();
    });
    expect(screen.getByText('Live')).toBeInTheDocument();

    // LIVE and ROTATING show no banner at all, whatever the detail says.
    act(() => {
      socket?.message({ type: 'status', stage_id: 'main', state: 'LIVE', detail: 'session 2' });
    });
    expect(screen.queryByText(/^Captions /)).toBeNull();
    act(() => {
      socket?.message({
        type: 'status',
        stage_id: 'main',
        state: 'ROTATING',
        detail: 'GoAway: session 3',
      });
    });
    expect(screen.queryByText(/^Captions /)).toBeNull();
    expect(screen.queryByText(/session/)).toBeNull();

    act(() => {
      socket?.message({ type: 'status', stage_id: 'main', state: 'STOPPED', detail: null });
    });
    expect(screen.getByText('Captions have ended for this stage.')).toBeInTheDocument();
  });

  it('exposes the stage name as the heading and the connection state as a status badge', async () => {
    renderPage('/live/main?lang=es');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Main Stage' }),
    ).toBeInTheDocument();

    const badge = screen.getByText('Connecting…');
    expect(badge).toHaveAttribute('role', 'status');

    act(() => {
      FakeSocket.instances[0]?.open();
    });
    expect(screen.getByText('Live')).toHaveAttribute('role', 'status');

    // The status banner is a polite status, not an alert, and the stage badge sits inside it.
    const banner = screen
      .getByText('Captions are running with reduced quality.')
      .closest('[role="status"]');
    expect(banner).not.toBeNull();
    expect(within(banner as HTMLElement).getByText('DEGRADED')).toBeInTheDocument();

    // The language picker lives on the page with its accessible name.
    expect(screen.getByRole('radiogroup', { name: 'Caption language' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Spanish' })).toBeChecked();
  });

  it('lets the audience choose how many caption lines to show', () => {
    renderPage('/live/main?lang=es');
    const socket = FakeSocket.instances[0];
    act(() => {
      socket?.open();
      for (let seq = 1; seq <= 6; seq += 1) socket?.message(finalCaption(seq));
    });

    const region = screen.getByRole('region', { name: 'Captions' });
    expect(
      within(region)
        .getAllByText(/^line \d$/)
        .map((el) => el.textContent),
    ).toEqual(['line 4', 'line 5', 'line 6']);

    const lines = screen.getByRole('radiogroup', { name: 'Caption lines' });
    expect(within(lines).getByRole('radio', { name: '3 lines' })).toBeChecked();
    fireEvent.click(within(lines).getByRole('radio', { name: '5 lines' }));
    expect(within(lines).getByRole('radio', { name: '5 lines' })).toBeChecked();
    expect(within(region).getAllByText(/^line \d$/)).toHaveLength(5);

    // The display settings sit next to it.
    expect(screen.getByRole('group', { name: 'Display settings' })).toBeInTheDocument();
  });

  it('turns p50/p95 into a plain caption-delay line and hides it without data', () => {
    renderPage('/live/main?lang=es');
    const socket = FakeSocket.instances[0];
    act(() => {
      socket?.open();
      socket?.message({
        type: 'metrics',
        stage_id: 'main',
        p50_ms: 0,
        p95_ms: 0,
        rotations: 0,
        errors: 0,
      });
    });
    expect(screen.queryByText(/Caption delay/)).toBeNull();

    act(() => {
      socket?.message({
        type: 'metrics',
        stage_id: 'main',
        p50_ms: 870,
        p95_ms: 1640,
        rotations: 2,
        errors: 1,
      });
    });
    expect(
      screen.getByText('Caption delay: about 0.9 s (typical), 1.6 s (peak)'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/rotations|errors|p50|p95/)).toBeNull();
  });

  it('reports an unknown stage as an alert with a way back', async () => {
    renderPage('/live/nope?lang=es');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Unknown stage “nope”.');
    expect(within(alert).getByRole('link', { name: 'Back to the stage list' })).toHaveAttribute(
      'href',
      '/',
    );
  });
});
