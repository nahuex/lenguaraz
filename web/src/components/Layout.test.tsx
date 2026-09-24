// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { Layout } from './Layout';

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
  });

  it('shows the neutral defaults when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    renderShell();
    expect(await screen.findByText('Lenguaraz')).toBeInTheDocument();
    expect(screen.getByText('Live captions and translation')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });

  it('renders the event identity from /api/branding', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          event_name: 'My Conference 2026',
          tagline: 'Captions for everyone',
          primary_color: '#7c3aed',
          logo_url: '/branding/logo.svg',
          footer: 'Powered by Lenguaraz',
        }),
      }),
    );
    renderShell();
    expect(await screen.findByText('My Conference 2026')).toBeInTheDocument();
    expect(screen.getByText('Captions for everyone')).toBeInTheDocument();
    expect(screen.getByText('Powered by Lenguaraz')).toBeInTheDocument();
    expect(screen.getByRole('presentation', { hidden: true })).toHaveAttribute(
      'src',
      '/branding/logo.svg',
    );
    await waitFor(() =>
      expect(document.documentElement.style.getPropertyValue('--brand')).toBe('#7c3aed'),
    );
  });
});
