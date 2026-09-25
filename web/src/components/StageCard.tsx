// SPDX-License-Identifier: Apache-2.0
import { Link } from 'react-router-dom';
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
    <article
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-lg border border-line bg-surface-raised p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={headingId} className="text-lg font-semibold">
          {stage.name}
        </h2>
        <StateBadge state={stage.state} />
      </div>
      {stage.detail && <p className="text-sm text-ink-muted">{stage.detail}</p>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-ink-muted">Spoken language</dt>
        <dd>{spoken.length > 0 ? spoken.join(', ') : '—'}</dd>
        <dt className="text-ink-muted">Captions in</dt>
        <dd>{captionsIn.length > 0 ? captionsIn.join(', ') : '—'}</dd>
        <dt className="text-ink-muted">Watching now</dt>
        <dd>{stage.listeners}</dd>
      </dl>
      <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-2">
        <Link
          to={`/live/${encodeURIComponent(stage.id)}`}
          className="inline-flex w-fit items-center rounded-md bg-accent px-4 py-2 font-semibold text-accent-ink hover:opacity-90"
        >
          Open live captions
          <span className="sr-only"> for {stage.name}</span>
        </Link>
        <Link to={overlayHref} className="text-sm text-accent underline">
          Overlay for OBS
          <span className="sr-only"> for {stage.name}</span>
        </Link>
      </div>
    </article>
  );
}
