// SPDX-License-Identifier: Apache-2.0
import { Link, Outlet } from 'react-router-dom';
import { useBranding } from '../lib/useBranding';

/** Page shell: skip link, branded header, 16 px side gutters, centred column, footer. */
export function Layout() {
  const branding = useBranding();
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header
        className="border-b-4 border-line"
        style={{ borderColor: 'var(--brand)' }}
        data-testid="brand-header"
      >
        <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-4 py-3">
          {branding.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-8 w-auto" width={32} height={32} />
          ) : null}
          <div className="min-w-0">
            <Link to="/" className="text-lg font-semibold tracking-tight hover:underline">
              {branding.event_name}
            </Link>
            <p className="truncate text-sm text-ink-muted">{branding.tagline}</p>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-5xl px-4 py-4 text-sm text-ink-muted">
        {branding.footer}
      </footer>
    </div>
  );
}
