// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ADMIN_TOKEN_KEY, Mangrullo, formatCost, sumTokens } from './Mangrullo';
import type { AdminStage, Health } from '../lib/api';

const HEALTH: Health = { status: 'ok', engine: 'fake', stages: 2, version: '0.1.0' };

function adminStage(overrides: Partial<AdminStage>): AdminStage {
  return {
    id: 'main',
    name: 'Main Stage',
    state: 'LIVE',
    detail: 'session 2',
    source_lang: ['en-US'],
    targets: ['es'],
    languages: ['en', 'es'],
    active_languages: ['es'],
    listeners: 4,
    dry_run: true,
    session_id: 'abc',
    rotations: 1,
    errors: 0,
    duplicates_dropped: 2,
    last_rotation_gap_ms: 120,
    chunks_dropped: 0,
    captions_final: 42,
    p50_ms: 850.4,
    p95_ms: 1600,
    interim_p95_ms: 500,
    translation_tokens: { es: { input: 1000, output: 400, total: 1400, calls: 20 } },
    audio_seconds: 600,
    est_cost_usd: 0.1234,
    transcript_entries: { en: 42, es: 42 },
    running: true,
    ...overrides,
  };
}

const STAGES: AdminStage[] = [
  adminStage({}),
  adminStage({
    id: 'workshop',
    name: 'Workshop Room',
    state: 'STOPPED',
    detail: null,
    listeners: 0,
    running: false,
    est_cost_usd: 0.5,
    translation_tokens: {},
    active_languages: [],
  }),
];

type FetchMock = ReturnType<typeof vi.fn>;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** fetch stub that routes by path; `adminStatus` controls the admin endpoints. */
function stubFetch(adminStatus: 200 | 401): FetchMock {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === '/healthz') return json(HEALTH);
    if (adminStatus === 401) return json({ detail: 'invalid or missing admin token' }, 401);
    if (url === '/api/admin/stages') return json(STAGES);
    const control = /^\/api\/admin\/stages\/([^/]+)\/(start|stop)$/.exec(url);
    if (control && init?.method === 'POST') {
      const running = control[2] === 'start';
      return json({ id: control[1], state: running ? 'STARTING' : 'STOPPED', running });
    }
    return json({ detail: 'not found' }, 404);
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/mangrullo']}>
      <Mangrullo />
    </MemoryRouter>,
  );
}

function connectWith(token: string): void {
  fireEvent.change(screen.getByLabelText('Admin token'), { target: { value: token } });
  fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
}

describe('helpers', () => {
  it('sums tokens across languages and formats cost with 4 decimals', () => {
    expect(
      sumTokens({
        es: { input: 10, output: 5, total: 15, calls: 1 },
        pt: { input: 1, output: 2, total: 3, calls: 1 },
      }),
    ).toEqual({ input: 11, output: 7 });
    expect(formatCost(0.12345)).toBe('$0.1235');
    expect(formatCost(0)).toBe('$0.0000');
  });
});

describe('Mangrullo', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders only the token form and the health summary without a token', async () => {
    stubFetch(200);
    renderPage();

    expect(screen.getByRole('heading', { name: 'Mangrullo · operations' })).toBeInTheDocument();
    expect(screen.getByLabelText('Admin token')).toHaveAttribute('type', 'password');
    expect(screen.getByRole('button', { name: 'Connect' })).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByRole('region', { name: 'Stages' })).toBeNull();

    expect(await screen.findByText(/engine fake · 2 stages · version 0\.1\.0/)).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('shows "Invalid token" on 401 and clears the stored token', async () => {
    stubFetch(401);
    renderPage();
    connectWith('wrong');

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid token');
    expect(window.sessionStorage.getItem(ADMIN_TOKEN_KEY)).toBeNull();
    expect(screen.getByRole('button', { name: 'Connect' })).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('lists the stages with state badges and cost, and stops a stage with the Bearer header', async () => {
    const fetchMock = stubFetch(200);
    renderPage();
    connectWith('secret');

    const table = await screen.findByRole('table');
    expect(window.sessionStorage.getItem(ADMIN_TOKEN_KEY)).toBe('secret');
    expect(within(table).getByText('Main Stage', { selector: 'strong' })).toBeInTheDocument();
    expect(within(table).getByText('Workshop Room', { selector: 'strong' })).toBeInTheDocument();

    const badges = within(table).getAllByText(/^(LIVE|STOPPED)$/);
    expect(badges.map((el) => el.getAttribute('data-state'))).toEqual(['LIVE', 'STOPPED']);
    expect(within(table).getByText('$0.1234')).toBeInTheDocument();
    expect(within(table).getByText('$0.5000')).toBeInTheDocument();
    // Totals row: LIVE / total, listeners and cost sum.
    expect(within(table).getByText('1 LIVE / 2')).toBeInTheDocument();
    expect(within(table).getByText('$0.6234')).toBeInTheDocument();

    const listCall = fetchMock.mock.calls.find((call) => String(call[0]) === '/api/admin/stages');
    expect(listCall?.[1]).toMatchObject({ headers: { Authorization: 'Bearer secret' } });

    // Start is disabled while running, Stop while stopped.
    expect(screen.getByRole('button', { name: 'Start Main Stage' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Stop Workshop Room' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Start Workshop Room' })).toBeEnabled();

    const stop = screen.getByRole('button', { name: 'Stop Main Stage' });
    expect(stop).toBeEnabled();
    fireEvent.click(stop);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        (entry) => String(entry[0]) === '/api/admin/stages/main/stop',
      );
      expect(call).toBeDefined();
      expect(call?.[1]).toMatchObject({
        method: 'POST',
        headers: { Authorization: 'Bearer secret' },
      });
    });

    // The row reflects the control response until the next poll.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Start Main Stage' })).toBeEnabled();
    });

    // Links to the viewer and the overlay for each stage.
    expect(screen.getByRole('link', { name: 'Fogón for Main Stage' })).toHaveAttribute(
      'href',
      '/fogon/main',
    );
    expect(screen.getByRole('link', { name: 'Overlay for Main Stage' })).toHaveAttribute(
      'href',
      '/pizarron/main?lang=en',
    );
  });
});
