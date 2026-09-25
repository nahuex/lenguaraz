// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { setPref } from '../lib/prefs';

const BRANDING = {
  event_name: 'My Conference 2026',
  tagline: 'Captions for everyone',
  primary_color: '#7c3aed',
  logo_url: '/branding/logo.svg',
  footer: 'Powered by Lenguaraz',
};

function stubBrandingFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => BRANDING }),
  );
}

function rootToken(name: string): string {
  return document.documentElement.style.getPropertyValue(name);
}

function renderShell(): void {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        element: <Layout />,
        children: [{ index: true, element: <p>page</p> }],
      },
    ],
    { initialEntries: ['/'] },
  );
  render(<RouterProvider router={router} />);
}

describe('Layout branding', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setPref('highContrast', false);
  });

  it('shows the neutral defaults when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    renderShell();
    expect(await screen.findByText('Lenguaraz')).toBeInTheDocument();
    expect(screen.getByText('Live captions and translation')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('renders the event identity from /api/branding', async () => {
    stubBrandingFetch();
    renderShell();
    expect(await screen.findByText('My Conference 2026')).toBeInTheDocument();
    expect(screen.getByText('Captions for everyone')).toBeInTheDocument();
    expect(screen.getByText('Powered by Lenguaraz')).toBeInTheDocument();
    expect(screen.getByRole('presentation', { hidden: true })).toHaveAttribute(
      'src',
      '/branding/logo.svg',
    );
    await waitFor(() => expect(rootToken('--brand')).toBe('#7c3aed'));
  });

  it('maps the brand color onto --primary and --ring with a readable foreground', async () => {
    stubBrandingFetch();
    renderShell();
    await waitFor(() => expect(rootToken('--primary')).toBe('#7c3aed'));
    expect(rootToken('--ring')).toBe('#7c3aed');
    expect(rootToken('--primary-foreground')).toBe('#ffffff');
  });

  it('leaves the AAA high-contrast --primary untouched, even when toggled after loading', async () => {
    stubBrandingFetch();
    renderShell();
    await waitFor(() => expect(rootToken('--primary')).toBe('#7c3aed'));

    act(() => setPref('highContrast', true));
    await waitFor(() => expect(rootToken('--primary')).toBe(''));
    expect(rootToken('--ring')).toBe('');
    expect(rootToken('--primary-foreground')).toBe('');
    expect(rootToken('--brand')).toBe('#7c3aed');

    act(() => setPref('highContrast', false));
    await waitFor(() => expect(rootToken('--primary')).toBe('#7c3aed'));
  });
});
