// SPDX-License-Identifier: Apache-2.0

/** Lifecycle state of a stage as reported by the backend. */
export type StageState =
  | 'IDLE'
  | 'STARTING'
  | 'LIVE'
  | 'ROTATING'
  | 'DEGRADED'
  | 'STOPPED';

/** One entry of `GET /api/stages`. */
export interface Stage {
  id: string;
  name: string;
  state: StageState;
  detail: string | null;
  /** BCP-47 tags, e.g. `en-US`. */
  source_lang: string[];
  /** Short translation target codes, e.g. `es`. */
  targets: string[];
  listeners: number;
  dry_run: boolean;
}

/** Response of `GET /healthz`. */
export interface Health {
  status: string;
  engine: 'gemini' | 'fake';
  stages: number;
  version?: string;
}

/** Token usage of one translation target, as reported by the admin API. */
export interface TranslationTokens {
  input: number;
  output: number;
  total: number;
  calls: number;
}

/** One entry of `GET /api/admin/stages` (Bearer). */
export interface AdminStage extends Stage {
  /** Every caption language the stage can serve (sources + targets, short codes). */
  languages: string[];
  /** Languages with at least one listener right now. */
  active_languages: string[];
  session_id: string | null;
  rotations: number;
  errors: number;
  duplicates_dropped: number;
  last_rotation_gap_ms: number | null;
  chunks_dropped: number;
  captions_final: number;
  p50_ms: number | null;
  p95_ms: number | null;
  interim_p95_ms: number | null;
  translation_tokens: Record<string, TranslationTokens>;
  audio_seconds: number;
  est_cost_usd: number;
  transcript_entries: Record<string, number>;
  running: boolean;
}

/** Response of `POST /api/admin/stages/{id}/start|stop`. */
export interface StageControlResult {
  id: string;
  state: StageState;
  running: boolean;
}

export type ExportFormat = 'srt' | 'vtt' | 'txt';

export interface ExportResult {
  blob: Blob;
  filename: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** Build the error for a non-2xx response, using the JSON `detail` when present. */
async function errorFor(path: string, response: Response): Promise<ApiError> {
  let message = `${path} returned ${response.status}`;
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string' && detail.trim() !== '') {
      message = detail;
    }
  } catch {
    // Not JSON; keep the generic message.
  }
  return new ApiError(response.status, message);
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: 'application/json' },
    signal,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `${path} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchStages(signal?: AbortSignal): Promise<Stage[]> {
  return getJson<Stage[]>('/api/stages', signal);
}

export function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return getJson<Health>('/healthz', signal);
}

function bearer(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function adminJson<T>(
  token: string,
  path: string,
  method: 'GET' | 'POST',
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { Accept: 'application/json', ...bearer(token) },
    signal,
  });
  if (!response.ok) {
    throw await errorFor(path, response);
  }
  return (await response.json()) as T;
}

/** `GET /api/admin/stages` with the admin Bearer token. */
export function fetchAdminStages(token: string, signal?: AbortSignal): Promise<AdminStage[]> {
  return adminJson<AdminStage[]>(token, '/api/admin/stages', 'GET', signal);
}

export function startStage(token: string, id: string): Promise<StageControlResult> {
  return adminJson<StageControlResult>(
    token,
    `/api/admin/stages/${encodeURIComponent(id)}/start`,
    'POST',
  );
}

export function stopStage(token: string, id: string): Promise<StageControlResult> {
  return adminJson<StageControlResult>(
    token,
    `/api/admin/stages/${encodeURIComponent(id)}/stop`,
    'POST',
  );
}

/** Extract the file name from a `Content-Disposition: attachment; filename="..."` header. */
export function parseAttachmentFilename(header: string | null): string | null {
  if (header === null) return null;
  const extended = /filename\*=(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      // Fall through to the plain form.
    }
  }
  const plain = /filename="?([^";]+)"?/.exec(header);
  return plain?.[1]?.trim() || null;
}

/**
 * `GET /api/admin/stages/{id}/export?format=&lang=` (Bearer). Resolves with the
 * transcript as a Blob plus the file name suggested by the server (or
 * `<id>-<lang>.<format>` when the header is missing).
 */
export async function exportTranscript(
  token: string,
  id: string,
  format: ExportFormat,
  lang: string,
): Promise<ExportResult> {
  const query = new URLSearchParams({ format, lang });
  const path = `/api/admin/stages/${encodeURIComponent(id)}/export?${query.toString()}`;
  const response = await fetch(path, { headers: bearer(token) });
  if (!response.ok) {
    throw await errorFor(path, response);
  }
  const blob = await response.blob();
  const filename =
    parseAttachmentFilename(response.headers.get('Content-Disposition')) ??
    `${id}-${lang}.${format}`;
  return { blob, filename };
}
