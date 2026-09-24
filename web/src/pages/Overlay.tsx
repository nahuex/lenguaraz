// SPDX-License-Identifier: Apache-2.0
import { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  applyEvent,
  connectCaptions,
  initialCaptionState,
  type CaptionState,
  type ConnectionState,
} from '../lib/captions';
import { deriveShortCode } from '../lib/lang';
import { useStages } from '../lib/useStages';
import './overlay.css';

/**
 * Overlay: a transparent caption overlay for OBS / vMix browser sources.
 * Query parameters: `lang` (short code), `lines` (1-5), `size` (s|m|l|xl),
 * `align` (bottom|top), `bg` (band|none).
 */

export type OverlaySize = 's' | 'm' | 'l' | 'xl';
export type OverlayAlign = 'bottom' | 'top';
export type OverlayBackground = 'band' | 'none';

export interface OverlayOptions {
  lines: number;
  size: OverlaySize;
  align: OverlayAlign;
  bg: OverlayBackground;
}

export const MIN_LINES = 1;
export const MAX_LINES = 5;

/** Base font size in px per size step; scaled down with the viewport on small screens. */
export const OVERLAY_FONT_PX: Record<OverlaySize, number> = { s: 28, m: 40, l: 56, xl: 72 };

/** Viewport width (px) below which the font scales with the viewport. */
const SCALE_BELOW_PX = 640;

const SIZES: readonly OverlaySize[] = ['s', 'm', 'l', 'xl'];

export function parseOverlayOptions(params: URLSearchParams): OverlayOptions {
  const rawLines = Number.parseInt(params.get('lines') ?? '', 10);
  const lines = Number.isFinite(rawLines)
    ? Math.min(MAX_LINES, Math.max(MIN_LINES, rawLines))
    : 2;
  const rawSize = (params.get('size') ?? '').toLowerCase();
  const size = (SIZES as readonly string[]).includes(rawSize) ? (rawSize as OverlaySize) : 'l';
  const align = params.get('align') === 'top' ? 'top' : 'bottom';
  const bg = params.get('bg') === 'none' ? 'none' : 'band';
  return { lines, size, align, bg };
}

/** CSS font-size that caps at the step's px value and shrinks on narrow viewports. */
export function overlayFontSize(size: OverlaySize): string {
  const px = OVERLAY_FONT_PX[size];
  const vw = (px / SCALE_BELOW_PX) * 100;
  return `min(${px}px, ${vw.toFixed(3)}vw)`;
}

export function Overlay() {
  const { stage: stageId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const { stages } = useStages(5000);

  const options = useMemo(() => parseOverlayOptions(searchParams), [searchParams]);
  const stage = useMemo(() => stages?.find((s) => s.id === stageId) ?? null, [stages, stageId]);

  const requestedLang = searchParams.get('lang');
  const defaultLang = stage?.source_lang[0] ? deriveShortCode(stage.source_lang[0]) : null;
  const lang = requestedLang ?? defaultLang;

  const [captions, setCaptions] = useState<CaptionState>(initialCaptionState);
  const [connection, setConnection] = useState<ConnectionState>({
    status: 'connecting',
    attempt: 0,
  });

  useEffect(() => {
    document.title = stage ? `Overlay · ${stage.name}` : 'Overlay · Lenguaraz';
  }, [stage]);

  // Transparent page background, no scrollbars, no focus rings: scoped via <html data-overlay>.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.overlay = 'true';
    return () => {
      delete root.dataset.overlay;
    };
  }, []);

  useEffect(() => {
    if (!stageId || lang === null) return;
    setCaptions(initialCaptionState);
    setConnection({ status: 'connecting', attempt: 0 });
    const connection = connectCaptions({
      stageId,
      lang,
      onEvent: (event) => setCaptions((prev) => applyEvent(prev, event)),
      onConnection: setConnection,
    });
    return () => connection.close();
  }, [stageId, lang]);

  const stageMissing = stages !== null && stage === null;
  const errorLine =
    connection.status === 'error'
      ? `Overlay: ${connection.message ?? 'connection failed'} (stage "${stageId}", lang "${lang ?? '?'}")`
      : stageMissing
        ? `Overlay: unknown stage "${stageId}"`
        : null;

  const visible = captions.finals.slice(-options.lines);
  const hasText = visible.length > 0 || captions.interim !== null;

  return (
    <div className="overlay-root" data-align={options.align} data-size={options.size}>
      {errorLine !== null && (
        <p role="alert" className="overlay-error">
          {errorLine}
        </p>
      )}
      {stage?.dry_run && (
        <p className="overlay-tag" aria-label="Dry run: fake engine">
          DRY-RUN
        </p>
      )}
      {hasText && (
        <section
          aria-label="Captions"
          aria-live="polite"
          aria-atomic="false"
          className="overlay-captions"
          data-bg={options.bg}
          style={{ fontSize: overlayFontSize(options.size) }}
        >
          {visible.map((caption) => (
            <p key={caption.seq} className="overlay-line" data-seq={caption.seq} data-final="true">
              {caption.text}
            </p>
          ))}
          {captions.interim !== null && (
            <p
              className="overlay-line"
              data-seq={captions.interim.seq}
              data-interim="true"
              aria-live="off"
            >
              {captions.interim.text}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
