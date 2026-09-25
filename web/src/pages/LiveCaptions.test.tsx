// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LiveCaptions } from './LiveCaptions';
import type { Stage } from '../lib/api';
import type { ServerEvent, WebSocketLike } from '../lib/captions';

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
});
