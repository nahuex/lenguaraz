// SPDX-License-Identifier: Apache-2.0
import type { StageState } from './api';

/** A caption line as sent by the backend over `WS /ws/{stage_id}`. */
export interface Caption {
  stage_id: string;
  /** Monotonic per stage; an interim and its final share the same seq. */
  seq: number;
  lang: string;
  source_lang: string;
  is_final: boolean;
  text: string;
  /** Source-language text, present when the caption is a translation. */
  original?: string;
  t_audio_ms: number;
  latency_ms: number;
  degraded?: boolean;
}

export interface CaptionEvent extends Caption {
  type: 'caption';
}

export interface StatusEvent {
  type: 'status';
  stage_id: string;
  state: StageState;
  detail: string | null;
}

export interface MetricsEvent {
  type: 'metrics';
  stage_id: string;
  p50_ms: number;
  p95_ms: number;
  rotations: number;
  errors: number;
}

export type ServerEvent = CaptionEvent | StatusEvent | MetricsEvent;

export interface StageStatus {
  state: StageState;
  detail: string | null;
}

export interface Metrics {
  p50_ms: number;
  p95_ms: number;
  rotations: number;
  errors: number;
}

export interface CaptionState {
  finals: Caption[];
  interim: Caption | null;
  status: StageStatus | null;
  metrics: Metrics | null;
}

/** Maximum number of final captions kept in memory. */
export const MAX_FINALS = 50;

export const initialCaptionState: CaptionState = {
  finals: [],
  interim: null,
  status: null,
  metrics: null,
};

function stripType(event: CaptionEvent): Caption {
  const { type: _type, ...caption } = event;
  return caption;
}

/**
 * Pure reducer for server events.
 * - A final replaces the interim with the same seq (or any older interim).
 * - A stale interim (its final already arrived) is ignored.
 * - Finals are deduplicated by seq and capped at MAX_FINALS (oldest dropped).
 */
export function applyEvent(state: CaptionState, event: ServerEvent): CaptionState {
  switch (event.type) {
    case 'caption': {
      const caption = stripType(event);
      if (caption.is_final) {
        const existing = state.finals.findIndex((f) => f.seq === caption.seq);
        let finals: Caption[];
        if (existing !== -1) {
          finals = state.finals.slice();
          finals[existing] = caption;
        } else {
          finals = [...state.finals, caption];
          if (finals.length > MAX_FINALS) {
            finals = finals.slice(finals.length - MAX_FINALS);
          }
        }
        const interim =
          state.interim !== null && state.interim.seq <= caption.seq ? null : state.interim;
        return { ...state, finals, interim };
      }
      // Interim: ignore if its final is already known.
      if (state.finals.some((f) => f.seq === caption.seq)) {
        return state;
      }
      return { ...state, interim: caption };
    }
    case 'status':
      return { ...state, status: { state: event.state, detail: event.detail } };
    case 'metrics':
      return {
        ...state,
        metrics: {
          p50_ms: event.p50_ms,
          p95_ms: event.p95_ms,
          rotations: event.rotations,
          errors: event.errors,
        },
      };
    default:
      return state;
  }
}

export type ConnectionStatus = 'connecting' | 'live' | 'reconnecting' | 'error';

export interface ConnectionState {
  status: ConnectionStatus;
  /** Human-readable detail, set for `error` (and optionally `reconnecting`). */
  message?: string;
  /** Reconnect attempt number (0 on the first connection). */
  attempt: number;
}

/** Close codes on which the client must stop reconnecting. */
export const FATAL_CLOSE_CODES: Readonly<Record<number, string>> = {
  4404: 'unknown stage',
  4400: 'unsupported language',
  4429: 'rate limited',
};

export const RECONNECT_BASE_MS = 500;
export const RECONNECT_MAX_MS = 8000;
export const RECONNECT_JITTER_MS = 250;
export const PING_INTERVAL_MS = 20000;

/** Minimal WebSocket surface used by the client (allows fakes in tests). */
export interface WebSocketLike {
  readyState: number;
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

export type WebSocketFactory = (url: string) => WebSocketLike;

export interface ConnectOptions {
  stageId: string;
  lang: string;
  onEvent: (event: ServerEvent) => void;
  onConnection: (state: ConnectionState) => void;
  /** Override the WebSocket base URL (`ws://host`); derived from location by default. */
  baseUrl?: string;
  /** Override the WebSocket constructor (tests). */
  createSocket?: WebSocketFactory;
  /** Random source for jitter (tests). */
  random?: () => number;
}

export interface CaptionConnection {
  close(): void;
}

export function buildSocketUrl(stageId: string, lang: string, baseUrl?: string): string {
  const base =
    baseUrl ??
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
  return `${base}/ws/${encodeURIComponent(stageId)}?lang=${encodeURIComponent(lang)}`;
}

export function reconnectDelay(attempt: number, random: () => number = Math.random): number {
  const exponential = Math.min(RECONNECT_BASE_MS * 2 ** attempt, RECONNECT_MAX_MS);
  return exponential + Math.floor(random() * RECONNECT_JITTER_MS);
}

function parseEvent(data: unknown): ServerEvent | null {
  if (typeof data !== 'string') return null;
  try {
    const parsed: unknown = JSON.parse(data);
    if (
      parsed !== null &&
      typeof parsed === 'object' &&
      typeof (parsed as { type?: unknown }).type === 'string'
    ) {
      return parsed as ServerEvent;
    }
  } catch {
    // Malformed frame; ignore it.
  }
  return null;
}

const OPEN_STATE = 1;

/**
 * Open a caption stream for a stage and language. Reconnects with exponential
 * backoff (500 ms doubling to 8 s plus jitter) on any close except the fatal
 * application codes 4404/4400/4429, which surface as `error`. Sends the text
 * `ping` every 20 s to keep the connection alive.
 */
export function connectCaptions(options: ConnectOptions): CaptionConnection {
  const createSocket: WebSocketFactory =
    options.createSocket ?? ((url) => new WebSocket(url) as unknown as WebSocketLike);
  const random = options.random ?? Math.random;
  const url = buildSocketUrl(options.stageId, options.lang, options.baseUrl);

  let socket: WebSocketLike | null = null;
  let attempt = 0;
  let closed = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;

  const stopPing = (): void => {
    if (pingTimer !== null) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  };

  const startPing = (ws: WebSocketLike): void => {
    stopPing();
    pingTimer = setInterval(() => {
      if (ws.readyState === OPEN_STATE) {
        try {
          ws.send('ping');
        } catch {
          // The socket is closing; the close handler takes over.
        }
      }
    }, PING_INTERVAL_MS);
  };

  const scheduleReconnect = (): void => {
    if (closed) return;
    const delay = reconnectDelay(attempt, random);
    attempt += 1;
    options.onConnection({ status: 'reconnecting', attempt, message: `retrying in ${delay} ms` });
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      open();
    }, delay);
  };

  const open = (): void => {
    if (closed) return;
    if (attempt === 0) {
      options.onConnection({ status: 'connecting', attempt });
    }
    let ws: WebSocketLike;
    try {
      ws = createSocket(url);
    } catch (error) {
      options.onConnection({
        status: 'error',
        attempt,
        message: error instanceof Error ? error.message : 'cannot open WebSocket',
      });
      return;
    }
    socket = ws;

    ws.onopen = () => {
      if (closed || socket !== ws) return;
      attempt = 0;
      options.onConnection({ status: 'live', attempt });
      startPing(ws);
    };

    ws.onmessage = (message) => {
      if (closed || socket !== ws) return;
      const event = parseEvent(message.data);
      if (event !== null) options.onEvent(event);
    };

    ws.onerror = () => {
      // A close event always follows; nothing to do here.
    };

    ws.onclose = (event) => {
      if (socket !== ws) return;
      socket = null;
      stopPing();
      if (closed) return;
      const fatal = FATAL_CLOSE_CODES[event.code];
      if (fatal !== undefined) {
        closed = true;
        options.onConnection({
          status: 'error',
          attempt,
          message: event.reason ? `${fatal} (${event.reason})` : fatal,
        });
        return;
      }
      scheduleReconnect();
    };
  };

  open();

  return {
    close() {
      if (closed) return;
      closed = true;
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      stopPing();
      const ws = socket;
      socket = null;
      if (ws !== null) {
        try {
          ws.close(1000, 'client closed');
        } catch {
          // Already closed.
        }
      }
    },
  };
}
