// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, RouterProvider, createMemoryRouter } from 'react-router-dom';
import { configureAxe } from 'vitest-axe';
import type { ReactNode } from 'react';
import { A11yControls } from '../components/A11yControls';
import { CaptionView } from '../components/CaptionView';
import { LanguagePicker } from '../components/LanguagePicker';
import { Layout } from '../components/Layout';
import { StageCard } from '../components/StageCard';
import { Admin } from '../pages/Admin';
import type { Stage } from '../lib/api';
import type { Caption } from '../lib/captions';
import { buildLanguageOptions } from '../lib/lang';
import { reloadPrefs } from '../lib/prefs';

/*
 * Automated accessibility pass (spec 012 FR-012-03 / AC-1): axe-core, through vitest-axe,
 * must report no violation on the building blocks of Home (StageCard), Live captions
 * (LanguagePicker, A11yControls, CaptionView), the page shell (Layout) and the Admin sign-in
 * form. Fragments are rendered inside a <main> landmark, where they live in the app, so the
 * "content outside landmarks" rule checks the components rather than the test harness.
 * jsdom has no layout engine, so the colour-contrast rule can only ever return "needs
 * review" here (and logs canvas warnings); it is switched off, as jest-axe does by default,
 * and contrast is covered by the token pairs in src/index.css (AA, AAA in high contrast)
 * and by the owner at checkpoint H-UI. Every other rule runs with axe's defaults.
 */
const axe = configureAxe({ rules: { 'color-contrast': { enabled: false } } });

const STAGE: Stage = {
  id: 'main',
  name: 'Main Stage',
  state: 'LIVE',
  detail: 'Keynote in progress',
  source_lang: ['en-US'],
  targets: ['es', 'pt'],
  listeners: 12,
  dry_run: false,
};

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

function renderInMain(children: ReactNode): HTMLElement {
  return render(
    <MemoryRouter>
      <main>{children}</main>
    </MemoryRouter>,
  ).container;
}

describe('accessibility (axe)', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    reloadPrefs();
    // No backend in tests: branding, health and stage requests fail and the pages fall back.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('StageCard', async () => {
    const container = renderInMain(<StageCard stage={STAGE} />);
    expect(screen.getByRole('article', { name: 'Main Stage' })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('LanguagePicker', async () => {
    const options = buildLanguageOptions(STAGE);
    const container = renderInMain(
      <LanguagePicker options={options} value="es" onChange={() => undefined} />,
    );
    expect(screen.getByRole('radiogroup', { name: 'Caption language' })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('A11yControls', async () => {
    const container = renderInMain(<A11yControls />);
    expect(screen.getByRole('group', { name: 'Display settings' })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('CaptionView with two finals, an interim and the original shown', async () => {
    const finals = [caption(1, 'Hola a todos.', 'Hello everyone.'), caption(2, 'Empecemos.')];
    const interim = { ...caption(3, 'Primero', 'First'), is_final: false };
    const container = renderInMain(
      <CaptionView finals={finals} interim={interim} lines={3} showOriginal={true} />,
    );
    const region = screen.getByRole('region', { name: 'Captions' });
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveAttribute('aria-atomic', 'false');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('Layout shell', async () => {
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
    const { container } = render(<RouterProvider router={router} />);
    expect(await screen.findByText('Lenguaraz')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('Admin sign-in form', async () => {
    const container = renderInMain(<Admin />);
    expect(await screen.findByText(/Backend unreachable/)).toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Admin sign-in' })).toBeInTheDocument();
    expect(screen.getByLabelText('Admin token')).toHaveAttribute('type', 'password');
    expect(await axe(container)).toHaveNoViolations();
  });
});
