// SPDX-License-Identifier: Apache-2.0
import { useCallback, useEffect, useId, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, CircleAlert, LogIn, LogOut, Play, Square } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
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
  type StageState,
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
  'Latency p50 / p95 (ms)',
  'Rotations · Errors · Duplicates · Dropped',
  'Tokens (in / out)',
  'Cost (USD)',
  'Actions',
  'Export',
] as const;

/**
 * Solid badge colours per stage state; each pair keeps >= 4.5:1 on its own so the badge
 * reads the same in every theme (the same pairs as components/StateBadge).
 */
const STATE_BADGE: Record<StageState, string> = {
  LIVE: 'bg-[#22c55e] text-[#052e16]',
  STARTING: 'bg-[#f59e0b] text-[#451a03]',
  ROTATING: 'bg-[#f59e0b] text-[#451a03]',
  DEGRADED: 'bg-[#f97316] text-[#431407]',
  IDLE: 'bg-[#9ca3af] text-[#111827]',
  STOPPED: 'bg-[#9ca3af] text-[#111827]',
};

/*
 * Below the `md` breakpoint the table turns into a stack of cards: the header row is
 * hidden, every row is a card and every cell is a labelled block. The explicit ARIA roles
 * keep the table semantics that browsers drop when the CSS display changes.
 */
const ROW =
  'mb-4 block rounded-xl border-b-0 bg-card p-3 ring-1 ring-foreground/10 md:mb-0 md:table-row md:rounded-none md:border-b md:p-0 md:ring-0';
const CELL = 'block px-0 py-1 whitespace-normal md:table-cell md:px-3 md:py-2 md:align-top';
const CELL_LABEL =
  'mr-2 inline-block min-w-[9rem] text-xs font-semibold uppercase tracking-wide text-muted-foreground md:hidden';
const SELECT =
  'h-7 rounded-md border border-input bg-transparent px-2 text-[0.8rem] text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30';

interface CellProps {
  label: string;
  children: ReactNode;
  className?: string;
  /** Render as the row header (`th scope="row"`): the stage name identifies the row. */
  header?: boolean;
}

/** Table cell that becomes a labelled block on phones (the table turns into cards). */
function Cell({ label, children, className, header = false }: CellProps) {
  const classes = cn(CELL, className);
  const tag = <span className={CELL_LABEL}>{label}</span>;
  return header ? (
    <TableHead scope="row" role="rowheader" className={cn('h-auto font-normal', classes)}>
      {tag}
      {children}
    </TableHead>
  ) : (
    <TableCell role="cell" className={classes}>
      {tag}
      {children}
    </TableCell>
  );
}

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
  const tokenHintId = `${tokenInputId}-hint`;

  useEffect(() => {
    document.title = 'Operator dashboard · Lenguaraz';
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
        action === 'start'
          ? await startStage(current, stage.id)
          : await stopStage(current, stage.id);
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
    <div className="flex flex-col gap-6">
      <nav aria-label="Breadcrumb" className="text-sm">
        <Button asChild variant="link" size="sm" className="h-auto px-0">
          <Link to="/">
            <ArrowLeft aria-hidden="true" />
            All stages
          </Link>
        </Button>
      </nav>

      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-bold tracking-tight">Operator dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {health !== null
            ? `Backend: engine ${health.engine} · ${health.stages} ${
                health.stages === 1 ? 'stage' : 'stages'
              }${health.version ? ` · version ${health.version}` : ''}`
            : healthError !== null
              ? `Backend unreachable (${healthError}).`
              : 'Checking backend…'}
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Operator access</CardTitle>
          <CardDescription id={tokenHintId}>
            {"The ADMIN_TOKEN value from the server's .env"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <form
            onSubmit={connect}
            aria-label="Admin sign-in"
            className="flex flex-wrap items-end gap-3"
          >
            <div className="grid min-w-0 flex-1 gap-2">
              <Label htmlFor={tokenInputId}>Admin token</Label>
              <Input
                id={tokenInputId}
                type="password"
                autoComplete="off"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={token !== null}
                placeholder={token !== null ? 'Signed in' : undefined}
                aria-describedby={tokenHintId}
              />
            </div>
            {token === null ? (
              <Button type="submit">
                <LogIn aria-hidden="true" />
                Sign in
              </Button>
            ) : (
              <Button type="button" variant="outline" onClick={() => clearToken(null)}>
                <LogOut aria-hidden="true" />
                Sign out
              </Button>
            )}
          </form>
          {authError !== null && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>{authError}</AlertTitle>
            </Alert>
          )}
        </CardContent>
      </Card>

      {token !== null && (
        <section aria-label="Stages" className="flex flex-col gap-3">
          {error !== null && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>Stage list unavailable</AlertTitle>
              <AlertDescription>
                {error}. Retrying every {POLL_MS / 1000} seconds.
              </AlertDescription>
            </Alert>
          )}
          {actionError !== null && (
            <Alert variant="destructive">
              <CircleAlert aria-hidden="true" />
              <AlertTitle>Request failed</AlertTitle>
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}

          {stages === null && error === null && (
            <div role="status" className="flex flex-col gap-2">
              <span className="sr-only">Loading stages…</span>
              {[0, 1, 2].map((row) => (
                <Skeleton key={row} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          )}

          {stages !== null && stages.length === 0 && (
            <p className="text-muted-foreground">No stages configured.</p>
          )}

          {stages !== null && stages.length > 0 && totals !== null && (
            <div className="md:overflow-hidden md:rounded-xl md:ring-1 md:ring-foreground/10">
              <Table role="table">
                <TableCaption className="sr-only">
                  Every stage with its live metrics, refreshed every {POLL_MS / 1000} seconds.
                </TableCaption>
                <TableHeader role="rowgroup" className="hidden bg-muted/50 md:table-header-group">
                  <TableRow role="row">
                    {HEADERS.map((header) => (
                      <TableHead
                        key={header}
                        role="columnheader"
                        scope="col"
                        className="px-3 text-xs uppercase tracking-wide text-muted-foreground"
                      >
                        {header}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody role="rowgroup">
                  {stages.map((stage) => {
                    const busy = pending[stage.id] === true;
                    const exporting = pending[`${stage.id}:export`] === true;
                    const tokens = sumTokens(stage.translation_tokens);
                    const lang = exportLang[stage.id] ?? defaultExportLang(stage);
                    const selectId = `export-lang-${stage.id}`;
                    return (
                      <TableRow key={stage.id} role="row" data-stage={stage.id} className={ROW}>
                        <Cell label="Stage" header>
                          <strong className="font-semibold">{stage.name}</strong>
                          <span className="ml-2 font-mono text-xs text-muted-foreground">
                            {stage.id}
                          </span>
                          {stage.dry_run && (
                            <Badge variant="outline" className="ml-2">
                              Dry run
                            </Badge>
                          )}
                        </Cell>
                        <Cell label="State">
                          <Badge
                            data-state={stage.state}
                            className={cn('font-semibold', STATE_BADGE[stage.state])}
                          >
                            {stage.state}
                          </Badge>
                          {stage.detail && (
                            <span
                              className="mt-1 block max-w-[14rem] truncate text-xs text-muted-foreground"
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
                        <Cell label="Latency p50 / p95 (ms)">
                          <span className="whitespace-nowrap">
                            {formatMs(stage.p50_ms)} / {formatMs(stage.p95_ms)}
                          </span>
                          <span className="block text-xs text-muted-foreground">
                            interim p95 {formatMs(stage.interim_p95_ms)}
                          </span>
                        </Cell>
                        <Cell label="Rotations · Errors · Duplicates · Dropped">
                          <span className="whitespace-nowrap">
                            {formatInt(stage.rotations)} · {formatInt(stage.errors)} ·{' '}
                            {formatInt(stage.duplicates_dropped)} ·{' '}
                            {formatInt(stage.chunks_dropped)}
                          </span>
                        </Cell>
                        <Cell label="Tokens (in / out)">
                          <span className="whitespace-nowrap">
                            {formatInt(tokens.input)} / {formatInt(tokens.output)}
                          </span>
                        </Cell>
                        <Cell label="Cost (USD)">
                          <span className="whitespace-nowrap font-mono">
                            {formatCost(stage.est_cost_usd)}
                          </span>
                        </Cell>
                        <Cell label="Actions">
                          <span className="inline-flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              disabled={busy || stage.running}
                              aria-label={`Start ${stage.name}`}
                              onClick={() => control(stage, 'start')}
                            >
                              <Play aria-hidden="true" />
                              Start
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy || !stage.running}
                              aria-label={`Stop ${stage.name}`}
                              onClick={() => control(stage, 'stop')}
                            >
                              <Square aria-hidden="true" />
                              Stop
                            </Button>
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
                                setExportLang((prev) => ({
                                  ...prev,
                                  [stage.id]: event.target.value,
                                }))
                              }
                              className={SELECT}
                            >
                              {(stage.languages.length > 0 ? stage.languages : [lang]).map(
                                (code) => (
                                  <option key={code} value={code}>
                                    {languageLabel(code)}
                                  </option>
                                ),
                              )}
                            </select>
                            {EXPORT_FORMATS.map((format) => (
                              <Button
                                key={format}
                                size="sm"
                                variant="outline"
                                disabled={exporting}
                                aria-label={`${format.toUpperCase()} export for ${stage.name}`}
                                onClick={() => download(stage, format)}
                              >
                                {format.toUpperCase()}
                              </Button>
                            ))}
                          </span>
                          <span className="mt-1 flex flex-wrap gap-3">
                            <Button
                              asChild
                              variant="link"
                              size="sm"
                              className="h-auto px-0 text-xs underline"
                            >
                              <Link
                                to={`/live/${encodeURIComponent(stage.id)}`}
                                aria-label={`Live captions for ${stage.name}`}
                              >
                                Live captions
                              </Link>
                            </Button>
                            <Button
                              asChild
                              variant="link"
                              size="sm"
                              className="h-auto px-0 text-xs underline"
                            >
                              <Link
                                to={overlayPath(stage)}
                                aria-label={`Overlay for ${stage.name}`}
                              >
                                Overlay
                              </Link>
                            </Button>
                          </span>
                        </Cell>
                      </TableRow>
                    );
                  })}
                </TableBody>
                <TableFooter role="rowgroup" className="border-t-0 bg-transparent md:border-t">
                  <TableRow role="row" className={cn(ROW, 'mb-0 font-semibold md:bg-muted/50')}>
                    <TableHead
                      role="rowheader"
                      scope="row"
                      className={cn(CELL, 'h-auto font-semibold')}
                    >
                      Totals
                    </TableHead>
                    <Cell label="Stages">
                      {totals.live} LIVE / {totals.total}
                    </Cell>
                    <Cell label="Listeners">{formatInt(totals.listeners)}</Cell>
                    <TableCell role="cell" className="hidden md:table-cell" colSpan={5} />
                    <Cell label="Cost (USD)">
                      <span className="font-mono">{formatCost(totals.cost)}</span>
                    </Cell>
                    <TableCell role="cell" className="hidden md:table-cell" colSpan={2} />
                  </TableRow>
                </TableFooter>
              </Table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
