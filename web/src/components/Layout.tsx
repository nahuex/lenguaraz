// SPDX-License-Identifier: Apache-2.0
import { Link, Outlet } from 'react-router-dom';
import { Separator } from '@/components/ui/separator';
import { useBranding } from '../lib/useBranding';

/**
 * Page shell: skip link, header with a brand stripe (--primary, driven by /api/branding),
 * 16 px side gutters, centred column, footer. Header and footer are set off with separators.
 */
export function Layout() {
  const branding = useBranding();
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="border-t-4 border-primary" data-testid="brand-header">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-4 py-3">
          {branding.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-8 w-auto" width={32} height={32} />
          ) : null}
          <div className="min-w-0">
            <Link
              to="/"
              className="text-lg font-semibold tracking-tight underline-offset-4 hover:underline"
            >
              {branding.event_name}
            </Link>
            <p className="truncate text-sm text-muted-foreground">{branding.tagline}</p>
          </div>
        </div>
      </header>
      <Separator />
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <Separator />
      <footer className="mx-auto w-full max-w-5xl px-4 py-4 text-sm text-muted-foreground">
        {branding.footer}
      </footer>
    </div>
  );
}
