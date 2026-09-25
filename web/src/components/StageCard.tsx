// SPDX-License-Identifier: Apache-2.0
import { Captions, Cast } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { Stage } from '../lib/api';
import { buildLanguageOptions, deriveShortCode, languageLabel } from '../lib/lang';
import { StateBadge } from './StateBadge';

interface StageCardProps {
  stage: Stage;
}

export function StageCard({ stage }: StageCardProps) {
  // Language names only (no BCP-47 tags): "English", not "English (en-US)".
  const spoken = Array.from(
    new Set(stage.source_lang.map((tag) => languageLabel(deriveShortCode(tag)))),
  );
  // Sources first, then translation targets, without duplicates.
  const captionsIn = buildLanguageOptions(stage).map((option) => option.label);
  const headingId = `stage-${stage.id}-name`;
  const firstSource = stage.source_lang[0];
  const overlayHref = firstSource
    ? `/overlay/${encodeURIComponent(stage.id)}?lang=${encodeURIComponent(deriveShortCode(firstSource))}`
    : `/overlay/${encodeURIComponent(stage.id)}`;

  return (
    // `ring-border` instead of the primitive's translucent ring so the card outline follows
    // the --border token (solid white in high contrast).
    <Card role="article" aria-labelledby={headingId} className="h-full ring-border">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">
          <h2 id={headingId}>{stage.name}</h2>
        </CardTitle>
        <CardAction>
          <StateBadge state={stage.state} />
        </CardAction>
        {stage.detail && <CardDescription>{stage.detail}</CardDescription>}
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          <dt className="text-muted-foreground">Spoken language</dt>
          <dd>{spoken.length > 0 ? spoken.join(', ') : '—'}</dd>
          <dt className="text-muted-foreground">Captions in</dt>
          <dd>{captionsIn.length > 0 ? captionsIn.join(', ') : '—'}</dd>
          <dt className="text-muted-foreground">Watching now</dt>
          <dd>{stage.listeners}</dd>
        </dl>
      </CardContent>
      <CardFooter className="mt-auto flex-wrap gap-2">
        {/* Visible text first, stage name appended (WCAG 2.5.3 label in name). */}
        <Button asChild size="lg">
          <Link
            to={`/live/${encodeURIComponent(stage.id)}`}
            aria-label={`Open live captions for ${stage.name}`}
          >
            <Captions aria-hidden="true" data-icon="inline-start" />
            Open live captions
          </Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link to={overlayHref} aria-label={`Overlay for OBS for ${stage.name}`}>
            <Cast aria-hidden="true" data-icon="inline-start" />
            Overlay for OBS
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
