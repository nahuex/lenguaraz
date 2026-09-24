// SPDX-License-Identifier: Apache-2.0
import { useCallback, useEffect, useId, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { StateBadge } from '../components/StateBadge';
import {
  ApiError,
  exportTranscript,
  fetchAdminStages,
  fetchHealth,
  startStage,
  stopStage,
  type AdminStage,
  type ExportFormat,
  type Health,
  type TranslationTokens,
} from '../lib/api';
import { deriveShortCode, languageLabel } from '../lib/lang';

/**
 * Admin: the operator dashboard. Bearer-authenticated view of every stage
 * with start/stop, transcript export and the live metrics, polled every 3 s.
 * The admin token lives in sessionStorage only (never in the URL).
 */

export const ADMIN_TOKEN_KEY = 'lenguaraz.adminToken';
export const POLL_MS = 3000;

const EXPORT_FORMATS: readonly ExportFormat[] = ['srt', 'vtt', 'txt'];

function readToken(): string | null {
  try {
    const value = window.sessionStorage.getItem(ADMIN_TOKEN_KEY);
    return value && value.trim() !== '' ? value : null;
  } catch {
    return null;
  }
}

function writeToken(token: string | null): void {
  try {
    if (token === null) {
      window.sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    } else {
      window.sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    }
  } catch {
    // Storage unavailable; the token still lives in component state.
  }
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

export function sumTokens(tokens: Record<string, TranslationTokens>): {
  input: number;
  output: number;
} {
  let input = 0;
  let output = 0;
  for (const usage of Object.values(tokens)) {
    input += usage.input;
    output += usage.output;
  }
  return { input, output };
}

function formatInt(value: number): string {
  return value.toLocaleString('en-US');
}

function formatMs(value: number | null): string {
  return value === null ? '—' : formatInt(Math.round(value));
}

export function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

function overlayPath(stage: AdminStage): string {
  const base = `/overlay/${encodeURIComponent(stage.id)}`;
  const source = stage.source_lang[0];
  return source ? `${base}?lang=${encodeURIComponent(deriveShortCode(source))}` : base;
}

function defaultExportLang(stage: AdminStage): string {
  const first = stage.languages[0] ?? stage.source_lang[0];
  return first ? deriveShortCode(first) : 'en';
}

/** Trigger a browser download for a Blob (object URL + synthetic anchor click). */
function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

interface AdminStagesPoll {
  stages: AdminStage[] | null;
  error: string | null;
  refresh: () => void;
  patch: (result: { id: string; state: AdminStage['state']; running: boolean }) => void;
}

/** Poll `GET /api/admin/stages` while a token is set; 401 hands control to `onUnauthorized`. */
function useAdminStages(token: string | null, onUnauthorized: () => void): AdminStagesPoll {
  const [stages, setStages] = useState<AdminStage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((value) => value + 1), []);
  const patch = useCallback<AdminStagesPoll['patch']>((result) => {
    setStages((prev) =>
      prev === null
        ? prev
        : prev.map((stage) =>
            stage.id === result.id
              ? { ...stage, state: result.state, running: result.running }
              : stage,
          ),
    );
  }, []);

  useEffect(() => {
    if (token === null) {
      setStages(null);
      setError(null);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();

    const load = async (): Promise<void> => {
      try {
        const result = await fetchAdminStages(token, controller.signal);
        if (cancelled) return;
        setStages(result);
        setError(null);
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) {
          onUnauthorized();
          return;
        }
        setError(errorMessage(err, 'backend unreachable'));
      }
    };

    void load();
    const timer = setInterval(() => {
      void load();
    }, POLL_MS);

    return () => {
      cancelled = true;
      controller.abort();
      clearInterval(timer);
    };
  }, [token, tick, onUnauthorized]);

  return { stages, error, refresh, patch };
}

const HEADERS = [
  'Stage',
  'State',
  'Listeners',
  'Active languages',
  'Captions',
  'Latency (ms)',
  'Rotations / errors / dups / dropped',
  'Tokens (in / out)',
  'Cost (USD)',
  'Actions',
  'Export',
] as const;

interface CellProps {
  label: string;
  children: ReactNode;
  className?: string;
}

/** Table cell that becomes a labelled block on phones (the table turns into cards). */
function Cell({ label, children, className = '' }: CellProps) {
  return (
    <td role="cell" className={`block py-1 md:table-cell md:px-3 md:py-2 md:align-top ${className}`}>
      <span className="mr-2 inline-block min-w-[9rem] text-xs font-semibold uppercase tracking-wide text-ink-muted md:hidden">
        {label}
      </span>
      {children}
    </td>
  );
}

const BUTTON =
  'rounded-md border px-2.5 py-1 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50';
const BUTTON_PRIMARY = `${BUTTON} border-accent bg-accent text-accent-ink hover:opacity-90`;
const BUTTON_PLAIN = `${BUTTON} border-line bg-surface-raised text-ink hover:border-accent`;

export function Admin() {
  const [token, setToken] = useState<string | null>(() => readToken());
  const [draft, setDraft] = useState('');
  const [authError, setAuthError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [exportLang, setExportLang] = useState<Record<string, string>>({});
  const tokenInputId = useId();

  useEffect(() => {
    document.title = 'Admin · Lenguaraz';
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((result) => {
        setHealth(result);
        setHealthError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setHealthError(errorMessage(err, 'backend unreachable'));
      });
    return () => controller.abort();
  }, []);

  const clearToken = useCallback((message: string | null) => {
    setToken(null);
    writeToken(null);
    setDraft('');
    setAuthError(message);
  }, []);

  const onUnauthorized = useCallback(() => clearToken('Invalid token'), [clearToken]);
  const { stages, error, refresh, patch } = useAdminStages(token, onUnauthorized);

  const connect = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const value = draft.trim();
    if (value === '') return;
    setAuthError(null);
    setActionError(null);
    writeToken(value);
    setToken(value);
  };

  const withPending = async (key: string, work: () => Promise<void>): Promise<void> => {
    setPending((prev) => ({ ...prev, [key]: true }));
    setActionError(null);
    try {
      await work();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
      } else {
        setActionError(errorMessage(err, 'request failed'));
      }
    } finally {
      setPending((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const control = (stage: AdminStage, action: 'start' | 'stop'): void => {
    if (token === null) return;
    const current = token;
    void withPending(stage.id, async () => {
      const result =
        action === 'start' ? await startStage(current, stage.id) : await stopStage(current, stage.id);
      patch(result);
      refresh();
    });
  };

  const download = (stage: AdminStage, format: ExportFormat): void => {
    if (token === null) return;
    const current = token;
    const lang = exportLang[stage.id] ?? defaultExportLang(stage);
    void withPending(`${stage.id}:export`, async () => {
      const result = await exportTranscript(current, stage.id, format, lang);
      saveBlob(result.blob, result.filename);
    });
  };

  const totals =
    stages === null
      ? null
      : {
          total: stages.length,
          live: stages.filter((stage) => stage.state === 'LIVE').length,
          listeners: stages.reduce((sum, stage) => sum + stage.listeners, 0),
          cost: stages.reduce((sum, stage) => sum + stage.est_cost_usd, 0),
        };

  return (
    <div className="flex flex-col gap-5">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Link to="/" className="text-accent underline">
          ← All stages
        </Link>
      </nav>

      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
        <p className="text-ink-muted">Operator dashboard</p>
        <p className="text-sm text-ink-muted">
          {health !== null
            ? `Backend: engine ${health.engine} · ${health.stages} ${
                health.stages === 1 ? 'stage' : 'stages'
              }${health.version ? ` · version ${health.version}` : ''}`
            : healthError !== null
              ? `Backend unreachable (${healthError}).`
              : 'Checking backend…'}
        </p>
      </header>

      <form
        onSubmit={connect}
        aria-label="Admin sign-in"
        className="flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface-raised p-4"
      >
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <label htmlFor={tokenInputId} className="text-sm font-semibold text-ink-muted">
            Admin token
          </label>
          <input
            id={tokenInputId}
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={token !== null}
            placeholder={token !== null ? 'connected' : 'ADMIN_TOKEN from the server .env'}
            className="w-full rounded-md border border-line bg-surface px-3 py-1.5 text-ink disabled:opacity-60"
          />
        </div>
        {token === null ? (
          <button type="submit" className={BUTTON_PRIMARY}>
            Connect
          </button>
        ) : (
          <button type="button" className={BUTTON_PLAIN} onClick={() => clearToken(null)}>
            Disconnect
          </button>
        )}
        {authError !== null && (
          <p role="alert" className="w-full text-sm font-semibold">
            {authError}
          </p>
        )}
      </form>

      {token !== null && (
        <section aria-label="Stages" className="flex flex-col gap-3">
          {error !== null && (
            <p role="alert" className="truncate rounded-md border border-line bg-surface-raised px-3 py-2 text-sm">
              Stage list unavailable ({error}). Retrying every {POLL_MS / 1000} seconds.
            </p>
          )}
          {actionError !== null && (
            <p role="alert" className="truncate rounded-md border border-line bg-surface-raised px-3 py-2 text-sm">
              Request failed: {actionError}
            </p>
          )}

          {stages === null && error === null && <p className="text-ink-muted">Loading stages…</p>}

          {stages !== null && stages.length === 0 && (
            <p className="text-ink-muted">No stages configured.</p>
          )}

          {stages !== null && stages.length > 0 && totals !== null && (
            <div className="md:overflow-x-auto md:rounded-lg md:border md:border-line">
              <table role="table" className="w-full border-collapse text-sm">
                <thead
                  role="rowgroup"
                  className="hidden bg-surface-raised text-left text-xs uppercase tracking-wide text-ink-muted md:table-header-group"
                >
                  <tr role="row">
                    {HEADERS.map((header) => (
                      <th
                        key={header}
                        role="columnheader"
                        scope="col"
                        className="whitespace-nowrap px-3 py-2 font-semibold"
                      >
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody role="rowgroup">
                  {stages.map((stage) => {
                    const busy = pending[stage.id] === true;
                    const exporting = pending[`${stage.id}:export`] === true;
                    const tokens = sumTokens(stage.translation_tokens);
                    const lang = exportLang[stage.id] ?? defaultExportLang(stage);
                    const selectId = `export-lang-${stage.id}`;
                    return (
                      <tr
                        key={stage.id}
                        role="row"
                        data-stage={stage.id}
                        className="mb-4 block rounded-lg border border-line bg-surface-raised p-3 md:mb-0 md:table-row md:rounded-none md:border-0 md:border-t md:border-line md:bg-transparent md:p-0"
                      >
                        <Cell label="Stage">
                          <strong className="font-semibold">{stage.name}</strong>
                          <span className="ml-2 font-mono text-xs text-ink-muted">{stage.id}</span>
                          {stage.dry_run && (
                            <span className="ml-2 rounded-sm border border-line px-1.5 py-0.5 text-xs font-semibold">
                              DRY-RUN
                            </span>
                          )}
                        </Cell>
                        <Cell label="State">
                          <StateBadge state={stage.state} />
                          {stage.detail && (
                            <span
                              className="mt-1 block max-w-[14rem] truncate text-xs text-ink-muted"
                              title={stage.detail}
                            >
                              {stage.detail}
                            </span>
                          )}
                        </Cell>
                        <Cell label="Listeners">{formatInt(stage.listeners)}</Cell>
                        <Cell label="Active languages">
                          {stage.active_languages.length > 0
                            ? stage.active_languages.map(languageLabel).join(', ')
                            : '—'}
                        </Cell>
                        <Cell label="Captions">{formatInt(stage.captions_final)}</Cell>
                        <Cell label="Latency (ms)">
                          <span className="whitespace-nowrap">
                            {formatMs(stage.p50_ms)} / {formatMs(stage.p95_ms)}
                          </span>
                          <span className="block text-xs text-ink-muted">
                            interim p95 {formatMs(stage.interim_p95_ms)}
                          </span>
                        </Cell>
                        <Cell label="Rot / err / dups / dropped">
                          <span className="whitespace-nowrap">
                            {formatInt(stage.rotations)} / {formatInt(stage.errors)} /{' '}
                            {formatInt(stage.duplicates_dropped)} / {formatInt(stage.chunks_dropped)}
                          </span>
                        </Cell>
                        <Cell label="Tokens (in / out)">
                          <span className="whitespace-nowrap">
                            {formatInt(tokens.input)} / {formatInt(tokens.output)}
                          </span>
                        </Cell>
                        <Cell label="Cost (USD)">
                          <span className="whitespace-nowrap font-mono">{formatCost(stage.est_cost_usd)}</span>
                        </Cell>
                        <Cell label="Actions">
                          <span className="inline-flex flex-wrap gap-2">
                            <button
                              type="button"
                              className={BUTTON_PRIMARY}
                              disabled={busy || stage.running}
                              aria-label={`Start ${stage.name}`}
                              onClick={() => control(stage, 'start')}
                            >
                              Start
                            </button>
                            <button
                              type="button"
                              className={BUTTON_PLAIN}
                              disabled={busy || !stage.running}
                              aria-label={`Stop ${stage.name}`}
                              onClick={() => control(stage, 'stop')}
                            >
                              Stop
                            </button>
                          </span>
                        </Cell>
                        <Cell label="Export">
                          <span className="inline-flex flex-wrap items-center gap-2">
                            <label htmlFor={selectId} className="sr-only">
                              Export language for {stage.name}
                            </label>
                            <select
                              id={selectId}
                              value={lang}
                              onChange={(event) =>
                                setExportLang((prev) => ({ ...prev, [stage.id]: event.target.value }))
                              }
                              className="rounded-md border border-line bg-surface px-2 py-1 text-sm text-ink"
                            >
                              {(stage.languages.length > 0 ? stage.languages : [lang]).map((code) => (
                                <option key={code} value={code}>
                                  {languageLabel(code)}
                                </option>
                              ))}
                            </select>
                            {EXPORT_FORMATS.map((format) => (
                              <button
                                key={format}
                                type="button"
                                className={BUTTON_PLAIN}
                                disabled={exporting}
                                aria-label={`${format.toUpperCase()} export for ${stage.name}`}
                                onClick={() => download(stage, format)}
                              >
                                {format.toUpperCase()}
                              </button>
                            ))}
                          </span>
                          <span className="mt-1 flex flex-wrap gap-3 text-xs">
                            <Link
                              to={`/live/${encodeURIComponent(stage.id)}`}
                              aria-label={`Live captions for ${stage.name}`}
                              className="text-accent underline"
                            >
                              Live captions
                            </Link>
                            <Link
                              to={overlayPath(stage)}
                              aria-label={`Overlay for ${stage.name}`}
                              className="text-accent underline"
                            >
                              Overlay
                            </Link>
                          </span>
                        </Cell>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot role="rowgroup">
                  <tr
                    role="row"
                    className="block rounded-lg border border-line bg-surface-raised p-3 font-semibold md:table-row md:rounded-none md:border-0 md:border-t-2 md:border-line md:p-0"
                  >
                    <th
                      role="rowheader"
                      scope="row"
                      className="block py-1 text-left md:table-cell md:px-3 md:py-2"
                    >
                      Totals
                    </th>
                    <Cell label="Stages">
                      {totals.live} LIVE / {totals.total}
                    </Cell>
                    <Cell label="Listeners">{formatInt(totals.listeners)}</Cell>
                    <td role="cell" className="hidden md:table-cell" colSpan={5} />
                    <Cell label="Cost (USD)">
                      <span className="font-mono">{formatCost(totals.cost)}</span>
                    </Cell>
                    <td role="cell" className="hidden md:table-cell" colSpan={2} />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
