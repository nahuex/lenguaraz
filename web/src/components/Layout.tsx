// SPDX-License-Identifier: Apache-2.0
import { Outlet } from 'react-router-dom';

/** Page shell: skip link, 16 px side gutters, centred column, footer. */
export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-5xl px-4 py-4 text-sm text-ink-muted">
        Lenguaraz · open source under Apache-2.0
      </footer>
    </div>
  );
}
