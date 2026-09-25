// SPDX-License-Identifier: Apache-2.0
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Info, TriangleAlert } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { A11yControls } from '../components/A11yControls';
import { CaptionView } from '../components/CaptionView';
import { ChoiceGroup, type ChoiceOption } from '../components/ChoiceGroup';
import { DryRunBadge } from '../components/DryRunBadge';
import { LanguagePicker } from '../components/LanguagePicker';
import { StateBadge } from '../components/StateBadge';
import {
  applyEvent,
  connectCaptions,
  initialCaptionState,
  type CaptionState,
  type ConnectionState,
  type ConnectionStatus,
} from '../lib/captions';
import type { StageState } from '../lib/api';
import { buildLanguageOptions } from '../lib/lang';
import { usePrefs } from '../lib/prefs';
import { useStages } from '../lib/useStages';

const LINE_OPTIONS = ['2', '3', '5'] as const;
type LineOption = (typeof LINE_OPTIONS)[number];

const LINE_CHOICES: readonly ChoiceOption<LineOption>[] = LINE_OPTIONS.map((count) => ({
  value: count,
  label: count,
  name: `${count} lines`,
}));

/** Audience-facing connection state: one sentence-case phrase, no technical detail. */
function connectionLabel(connection: ConnectionState): string {
  switch (connection.status) {
    case 'connecting':
      return 'Connecting…';
    case 'live':
      return 'Live';
    case 'reconnecting':
      return 'Reconnecting…';
    case 'error':
      return 'Connection failed';
  }
}

/**
 * Connection badge: the text carries the meaning; the dot only echoes it (amber while a
 * connection is pending, green when live, orange when it failed).
 */
const CONNECTION_BADGE: Record<
  ConnectionStatus,
  { variant: 'outline' | 'destructive'; dot: string }
> = {
  connecting: { variant: 'outline', dot: 'bg-[#f59e0b]' },
  live: { variant: 'outline', dot: 'bg-[#22c55e]' },
  reconnecting: { variant: 'outline', dot: 'bg-[#f59e0b]' },
  error: { variant: 'destructive', dot: 'bg-[#f97316]' },
};

/**
 * Audience-facing copy per stage state. LIVE and ROTATING (an internal session
 * handoff) show no banner; the raw `detail` string is never rendered here.
 */
const STATUS_COPY: Partial<Record<StageState, string>> = {
  IDLE: "Captions haven't started yet.",
  STARTING: 'Captions are starting…',
  DEGRADED: 'Captions are running with reduced quality.',
  STOPPED: 'Captions have ended for this stage.',
};

function formatSeconds(ms: number): string {
  return (ms / 1000).toFixed(1);
}

export function LiveCaptions() {
  const { stage: stageId = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const prefs = usePrefs();
  const { stages, error: stagesError } = useStages(5000);

  const stage = useMemo(() => stages?.find((s) => s.id === stageId) ?? null, [stages, stageId]);
  const options = useMemo(() => (stage ? buildLanguageOptions(stage) : []), [stage]);

  const requestedLang = searchParams.get('lang');
  const lang = requestedLang ?? options[0]?.code ?? null;

  const [lines, setLines] = useState<LineOption>('3');
  const [captions, setCaptions] = useState<CaptionState>(initialCaptionState);
  const [connection, setConnection] = useState<ConnectionState>({
    status: 'connecting',
    attempt: 0,
  });

  useEffect(() => {
    document.title = stage
      ? `Live captions · ${stage.name} · Lenguaraz`
      : 'Live captions · Lenguaraz';
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
  const statusCopy = status === null ? null : (STATUS_COPY[status.state] ?? null);
  const stageMissing = stages !== null && stage === null;
  const showPicker = options.length > 0 && lang !== null;
  const badge = CONNECTION_BADGE[connection.status];

  return (
    <div className="flex flex-col gap-5">
      <nav aria-label="Breadcrumb">
        <Button asChild variant="link" size="sm" className="h-auto px-0">
          <Link to="/">
            <ArrowLeft aria-hidden="true" />
            All stages
          </Link>
        </Button>
      </nav>

      <Card>
        <CardHeader>
          <CardTitle className="text-2xl font-bold tracking-tight">
            <h1>{stage?.name ?? stageId}</h1>
          </CardTitle>
          {stage?.dry_run && (
            <div>
              <DryRunBadge />
            </div>
          )}
          <CardAction>
            <Badge role="status" variant={badge.variant} className="gap-1.5">
              <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${badge.dot}`} />
              {connectionLabel(connection)}
            </Badge>
          </CardAction>
        </CardHeader>

        {(statusCopy !== null || showPicker) && (
          <CardContent className="flex flex-col gap-4">
            {status !== null && statusCopy !== null && (
              <Alert role="status">
                <Info aria-hidden="true" />
                <AlertTitle className="flex flex-wrap items-center gap-2">
                  <StateBadge state={status.state} />
                  <span>{statusCopy}</span>
                </AlertTitle>
              </Alert>
            )}
            {showPicker && lang !== null && (
              <LanguagePicker options={options} value={lang} onChange={changeLang} />
            )}
          </CardContent>
        )}
      </Card>

      {stageMissing && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Unknown stage “{stageId}”.</AlertTitle>
          <AlertDescription>
            <Link to="/">Back to the stage list</Link>.
          </AlertDescription>
        </Alert>
      )}

      {stagesError && stages === null && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>Backend unreachable ({stagesError}).</AlertTitle>
          <AlertDescription>Retrying every 5 seconds.</AlertDescription>
        </Alert>
      )}

      <CaptionView
        finals={captions.finals}
        interim={captions.interim}
        lines={Number(lines)}
        showOriginal={prefs.showOriginal}
      />

      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <ChoiceGroup
          label="Caption lines"
          options={LINE_CHOICES}
          value={lines}
          onChange={setLines}
        />
        <A11yControls />
      </div>

      {captions.metrics && captions.metrics.p50_ms > 0 && (
        <p className="text-sm text-muted-foreground">
          Caption delay: about {formatSeconds(captions.metrics.p50_ms)} s (typical),{' '}
          {formatSeconds(captions.metrics.p95_ms)} s (peak)
        </p>
      )}
    </div>
  );
}
