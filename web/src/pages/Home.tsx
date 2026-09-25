// SPDX-License-Identifier: Apache-2.0
import { WifiOff } from 'lucide-react';
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { DryRunBadge } from '../components/DryRunBadge';
import { StageCard } from '../components/StageCard';
import { useStages } from '../lib/useStages';

const GRID = 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3';
const SKELETON_CARDS = 3;

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
        <h1 className="text-3xl font-bold tracking-tight">Stages</h1>
        <p className="text-lg text-muted-foreground">
          Pick a stage to follow live captions in your language.
        </p>
      </header>

      {error && (
        <Alert variant="destructive">
          <WifiOff aria-hidden="true" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}. Retrying every 5 seconds.</AlertDescription>
        </Alert>
      )}

      {stages === null && !error && (
        <div className="flex flex-col gap-4">
          <p role="status" className="text-muted-foreground">
            Loading stages…
          </p>
          <div aria-hidden="true" className={GRID}>
            {Array.from({ length: SKELETON_CARDS }, (_, index) => (
              <Skeleton key={index} className="h-52 rounded-xl" />
            ))}
          </div>
        </div>
      )}

      {stages !== null && stages.length === 0 && (
        <p className="text-muted-foreground">No stages are configured yet.</p>
      )}

      {stages !== null && stages.length > 0 && (
        <section aria-label="Stages" className={GRID}>
          {stages.map((stage) => (
            <StageCard key={stage.id} stage={stage} />
          ))}
        </section>
      )}

      <p className="text-sm text-muted-foreground">
        <Link to="/admin" className="underline underline-offset-4 hover:text-foreground">
          Operator dashboard
        </Link>
      </p>
    </div>
  );
}
