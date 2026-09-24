// SPDX-License-Identifier: Apache-2.0
import { useEffect, useId, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { A11yControls } from '../components/A11yControls';
import { CaptionView } from '../components/CaptionView';
import { DryRunBadge } from '../components/DryRunBadge';
import { LanguagePicker } from '../components/LanguagePicker';
import { StateBadge } from '../components/StateBadge';
import {
  applyEvent,
  connectCaptions,
  initialCaptionState,
  type CaptionState,
  type ConnectionState,
} from '../lib/captions';
import { buildLanguageOptions } from '../lib/lang';
import { usePrefs } from '../lib/prefs';
import { useStages } from '../lib/useStages';

const LINE_OPTIONS = [2, 3, 5] as const;

function connectionLabel(connection: ConnectionState): string {
  switch (connection.status) {
    case 'connecting':
      return 'connecting';
    case 'live':
      return 'live';
    case 'reconnecting':
      return `reconnecting (attempt ${connection.attempt})`;
    case 'error':
      return `error: ${connection.message ?? 'connection failed'}`;
  }
}

const CONNECTION_DOT: Record<ConnectionState['status'], string> = {
  connecting: 'bg-[#f59e0b]',
  live: 'bg-[#22c55e]',
  reconnecting: 'bg-[#f59e0b]',
  error: 'bg-[#f97316]',
};

export function LiveCaptions() {
  const { stage: stageId = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const prefs = usePrefs();
  const { stages, error: stagesError } = useStages(5000);
  const linesGroupId = useId();

  const stage = useMemo(() => stages?.find((s) => s.id === stageId) ?? null, [stages, stageId]);
  const options = useMemo(() => (stage ? buildLanguageOptions(stage) : []), [stage]);

  const requestedLang = searchParams.get('lang');
  const lang = requestedLang ?? options[0]?.code ?? null;

  const [lines, setLines] = useState<number>(3);
  const [captions, setCaptions] = useState<CaptionState>(initialCaptionState);
  const [connection, setConnection] = useState<ConnectionState>({
    status: 'connecting',
    attempt: 0,
  });

  useEffect(() => {
    document.title = stage ? `Live captions · ${stage.name} · Lenguaraz` : 'Live captions · Lenguaraz';
  }, [stage]);

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

  const changeLang = (code: string): void => {
    setSearchParams({ lang: code }, { replace: true });
  };

  const status = captions.status ?? (stage ? { state: stage.state, detail: stage.detail } : null);
  const stageMissing = stages !== null && stage === null;

  return (
    <div className="flex flex-col gap-5">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link to="/" className="text-accent underline">
          ← All stages
        </Link>
      </nav>

      <header className="flex flex-col gap-2">
        {stage?.dry_run && (
          <div>
            <DryRunBadge />
          </div>
        )}
        <h1 className="text-2xl font-bold tracking-tight">
          {stage?.name ?? stageId}
        </h1>
        <p role="status" className="flex items-center gap-2 text-sm text-ink-muted">
          <span
            aria-hidden="true"
            className={`inline-block h-2.5 w-2.5 rounded-full ${CONNECTION_DOT[connection.status]}`}
          />
          Connection: {connectionLabel(connection)}
        </p>
      </header>

      {stageMissing && (
        <p role="alert" className="rounded-md border border-line bg-surface-raised px-4 py-3">
          Unknown stage “{stageId}”.{' '}
          <Link to="/" className="text-accent underline">
            Back to the stage list
          </Link>
          .
        </p>
      )}

      {stagesError && stages === null && (
        <p role="alert" className="rounded-md border border-line bg-surface-raised px-4 py-3">
          Backend unreachable ({stagesError}). Retrying every 5 seconds.
        </p>
      )}

      {status !== null && status.state !== 'LIVE' && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface-raised px-4 py-3"
        >
          <StateBadge state={status.state} />
          <span>
            Stage is {status.state.toLowerCase()}
            {status.detail ? ` — ${status.detail}` : ''}
          </span>
        </div>
      )}

      {options.length > 0 && lang !== null && (
        <LanguagePicker options={options} value={lang} onChange={changeLang} />
      )}

      <CaptionView
        finals={captions.finals}
        interim={captions.interim}
        lines={lines}
        showOriginal={prefs.showOriginal}
      />

      <div className="flex flex-wrap items-end gap-4">
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="mb-1 w-full text-sm font-semibold text-ink-muted">Caption lines</legend>
          {LINE_OPTIONS.map((count) => {
            const checked = lines === count;
            return (
              <label
                key={count}
                className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm font-medium has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus ${
                  checked ? 'border-accent bg-accent text-accent-ink' : 'border-line bg-surface-raised text-ink'
                }`}
              >
                <input
                  type="radio"
                  name={`lines-${linesGroupId}`}
                  value={count}
                  checked={checked}
                  onChange={() => setLines(count)}
                  className="sr-only"
                />
                {count}
              </label>
            );
          })}
        </fieldset>
        <A11yControls />
      </div>

      {captions.metrics && (
        <p className="text-sm text-ink-muted">
          Latency p50 {captions.metrics.p50_ms} ms · p95 {captions.metrics.p95_ms} ms · rotations{' '}
          {captions.metrics.rotations} · errors {captions.metrics.errors}
        </p>
      )}
    </div>
  );
}
