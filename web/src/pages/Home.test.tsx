// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Home } from './Home';
import type { Stage } from '../lib/api';

const STAGES: Stage[] = [
  {
    id: 'main',
    name: 'Main Stage',
    state: 'LIVE',
    detail: null,
    source_lang: ['en-US'],
    targets: ['es', 'pt'],
    listeners: 12,
    dry_run: true,
  },
  {
    id: 'workshop',
    name: 'Workshop Room',
    state: 'STOPPED',
    detail: 'Ends at 18:00',
    source_lang: ['es-AR'],
    targets: ['en'],
    listeners: 0,
    dry_run: false,
  },
];

function stubStages(body: unknown, status = 200): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

function renderHome(): void {
  render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  );
}

/** Text of the `<dd>` that follows the `<dt>` with the given term. */
function definition(card: HTMLElement, term: string): string | null {
  return within(card).getByText(term).nextElementSibling?.textContent ?? null;
}

describe('Home', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('shows the heading and a loading status before the first response', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>(() => {})),
    );
    renderHome();
    expect(screen.getByRole('heading', { level: 1, name: 'Stages' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Loading stages…');
    expect(screen.getByRole('link', { name: 'Operator dashboard' })).toHaveAttribute(
      'href',
      '/admin',
    );
  });

  it('lists every stage as a card with its state, languages and links', async () => {
    stubStages(STAGES);
    renderHome();
    const region = await screen.findByRole('region', { name: 'Stages' });
    const cards = within(region).getAllByRole('article');
    expect(cards).toHaveLength(2);

    const main = cards[0];
    expect(within(main).getByRole('heading', { level: 2, name: 'Main Stage' })).toBeInTheDocument();
    expect(within(main).getByText('LIVE')).toHaveAttribute('data-state', 'LIVE');
    expect(definition(main, 'Original audio')).toBe('English');
    expect(definition(main, 'Captions in (original + translations)')).toBe('English, Spanish, Portuguese');
    expect(definition(main, 'Watching now')).toBe('12');
    expect(
      within(main).getByRole('link', { name: 'Open live captions for Main Stage' }),
    ).toHaveAttribute('href', '/live/main');
    expect(
      within(main).getByRole('link', { name: 'Overlay for OBS for Main Stage' }),
    ).toHaveAttribute('href', '/overlay/main?lang=en');

    const workshop = cards[1];
    expect(within(workshop).getByText('STOPPED')).toHaveAttribute('data-state', 'STOPPED');
    expect(within(workshop).getByText('Ends at 18:00')).toBeInTheDocument();
    expect(definition(workshop, 'Original audio')).toBe('Spanish');
    expect(definition(workshop, 'Captions in (original + translations)')).toBe('Spanish, English');

    // One stage runs on the fake engine: the dry-run badge replaces the loading status.
    expect(screen.getByRole('status')).toHaveTextContent(
      'Dry run · simulated captions, no API key',
    );
  });

  it('says so when no stage is configured', async () => {
    stubStages([]);
    renderHome();
    expect(await screen.findByText('No stages are configured yet.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Stages' })).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('reports an unreachable backend as an alert and keeps retrying', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')));
    renderHome();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Backend unreachable');
    expect(alert).toHaveTextContent('Failed to fetch. Retrying every 5 seconds.');
    expect(screen.queryByRole('status')).toBeNull();
  });
});
