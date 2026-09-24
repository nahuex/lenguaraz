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
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
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
