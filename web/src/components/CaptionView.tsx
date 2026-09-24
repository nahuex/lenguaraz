// SPDX-License-Identifier: Apache-2.0
import type { Caption } from '../lib/captions';

interface CaptionViewProps {
  finals: Caption[];
  interim: Caption | null;
  /** How many final lines to show. */
  lines: number;
  /** Show the source-language text under a translated line. */
  showOriginal: boolean;
}

function hasDistinctOriginal(caption: Caption): caption is Caption & { original: string } {
  return (
    typeof caption.original === 'string' &&
    caption.original.trim() !== '' &&
    caption.original !== caption.text
  );
}

/**
 * The caption area: the last `lines` finals (newest at the bottom) in a
 * polite live region, plus the current interim line below them. The interim
 * line sits outside the live region so screen readers are not flooded.
 */
export function CaptionView({ finals, interim, lines, showOriginal }: CaptionViewProps) {
  const visible = finals.slice(-Math.max(1, lines));

  return (
    <div className="flex min-h-[40vh] flex-col justify-end gap-3 rounded-lg border border-line bg-surface-raised px-4 py-5">
      <section
        aria-label="Captions"
        aria-live="polite"
        aria-atomic="false"
        aria-relevant="additions text"
        className="flex flex-col gap-3"
      >
        {visible.length === 0 && interim === null && (
          <p className="caption-line text-caption text-ink-muted">Waiting for captions…</p>
        )}
        {visible.map((caption) => (
          <div key={caption.seq} data-seq={caption.seq} data-final="true">
            <p className="caption-line text-caption">
              {caption.text}
              {caption.degraded ? (
                <span
                  className="ml-2 align-middle text-[0.45em] font-medium uppercase tracking-wide text-ink-muted"
                  title="Translation unavailable right now; showing the original"
                >
                  original
                </span>
              ) : null}
            </p>
            {showOriginal && hasDistinctOriginal(caption) && (
              <p
                className="caption-line mt-1 text-[0.6em] text-ink-muted"
                lang={caption.source_lang}
              >
                {caption.original}
              </p>
            )}
          </div>
        ))}
      </section>
      {interim !== null && (
        <div data-seq={interim.seq} data-interim="true" aria-live="off">
          <p className="caption-line text-caption italic text-interim">{interim.text}</p>
          {showOriginal && hasDistinctOriginal(interim) && (
            <p
              className="caption-line mt-1 text-[0.6em] italic text-ink-muted"
              lang={interim.source_lang}
            >
              {interim.original}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
