// SPDX-License-Identifier: Apache-2.0
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { DryRunBadge } from '../components/DryRunBadge';
import { StageCard } from '../components/StageCard';
import { useStages } from '../lib/useStages';

export function Home() {
  const { stages, error } = useStages(5000);
  const dryRun = stages?.some((stage) => stage.dry_run) ?? false;

  useEffect(() => {
    document.title = 'Lenguaraz';
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        {dryRun && (
          <div>
            <DryRunBadge />
          </div>
        )}
        <h1 className="text-3xl font-bold tracking-tight">Lenguaraz</h1>
        <p className="text-lg text-ink-muted">the open-source interpreter for every stage</p>
      </header>

      {error && (
        <p role="alert" className="rounded-md border border-line bg-surface-raised px-4 py-3">
          Backend unreachable ({error}). Retrying every 5 seconds.
        </p>
      )}

      {stages === null && !error && <p className="text-ink-muted">Loading stages…</p>}

      {stages !== null && stages.length === 0 && (
        <p className="text-ink-muted">No stages configured yet.</p>
      )}

      {stages !== null && stages.length > 0 && (
        <section aria-label="Stages" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {stages.map((stage) => (
            <StageCard key={stage.id} stage={stage} />
          ))}
        </section>
      )}

      <p className="text-sm text-ink-muted">
        <Link to="/admin" className="underline hover:text-ink">
          Admin · operator dashboard
        </Link>
      </p>
    </div>
  );
}
