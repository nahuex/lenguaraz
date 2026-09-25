// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  applyEvent,
  buildSocketUrl,
  connectCaptions,
  initialCaptionState,
  MAX_FINALS,
  PING_INTERVAL_MS,
  socketBase,
  type CaptionEvent,
  type CaptionState,
  type ConnectionState,
  type ServerEvent,
  type WebSocketLike,
} from './captions';

describe('socketBase', () => {
  it('uses wss on an https page and ws otherwise (no mixed content)', () => {
    expect(socketBase({ protocol: 'https:', host: 'captions.example.org' })).toBe(
      'wss://captions.example.org',
    );
    expect(socketBase({ protocol: 'http:', host: 'localhost:8000' })).toBe('ws://localhost:8000');
  });

  it('derives the default from the current page location', () => {
    const expected = window.location.protocol === 'https:' ? 'wss' : 'ws';
    expect(socketBase()).toBe(`${expected}://${window.location.host}`);
    expect(buildSocketUrl('main', 'es')).toBe(
      `${expected}://${window.location.host}/ws/main?lang=es`,
    );
  });
});

function caption(seq: number, isFinal: boolean, text = `line ${seq}`): CaptionEvent {
  return {
    type: 'caption',
    stage_id: 'main',
    seq,
    lang: 'es',
    source_lang: 'en',
    is_final: isFinal,
    text,
    original: `original ${seq}`,
    t_audio_ms: seq * 1000,
    latency_ms: 900,
    degraded: false,
  };
}

function reduce(events: ServerEvent[], start: CaptionState = initialCaptionState): CaptionState {
  return events.reduce(applyEvent, start);
}

describe('applyEvent', () => {
  it('replaces an interim with the final that carries the same seq', () => {
    const state = reduce([caption(1, false, 'hel'), caption(1, true, 'hello')]);
    expect(state.interim).toBeNull();
    expect(state.finals).toHaveLength(1);
    expect(state.finals[0]?.text).toBe('hello');
  });

  it('shows a later interim with a new seq as the current interim', () => {
    const state = reduce([caption(1, false), caption(1, true), caption(2, false, 'wor')]);
    expect(state.finals).toHaveLength(1);
    expect(state.interim?.seq).toBe(2);
    expect(state.interim?.text).toBe('wor');
  });

  it('ignores a stale interim that arrives after its final', () => {
    const state = reduce([caption(1, true, 'hello'), caption(1, false, 'hel')]);
    expect(state.interim).toBeNull();
    expect(state.finals).toHaveLength(1);
    expect(state.finals[0]?.text).toBe('hello');
  });

  it('deduplicates finals by seq', () => {
    const state = reduce([caption(1, true, 'first'), caption(1, true, 'second')]);
    expect(state.finals).toHaveLength(1);
    expect(state.finals[0]?.text).toBe('second');
  });

  it('keeps at most 50 finals, dropping the oldest', () => {
    const events = Array.from({ length: MAX_FINALS + 10 }, (_, i) => caption(i + 1, true));
    const state = reduce(events);
    expect(state.finals).toHaveLength(MAX_FINALS);
    expect(state.finals[0]?.seq).toBe(11);
    expect(state.finals[MAX_FINALS - 1]?.seq).toBe(MAX_FINALS + 10);
  });

  it('records status and metrics events', () => {
    const state = reduce([
      { type: 'status', stage_id: 'main', state: 'ROTATING', detail: 'session 3' },
      { type: 'metrics', stage_id: 'main', p50_ms: 900, p95_ms: 1600, rotations: 3, errors: 0 },
    ]);
    expect(state.status).toEqual({ state: 'ROTATING', detail: 'session 3' });
    expect(state.metrics).toEqual({ p50_ms: 900, p95_ms: 1600, rotations: 3, errors: 0 });
    expect(state.finals).toHaveLength(0);
  });

  it('returns the same state object for unknown events', () => {
    const unknown = { type: 'mystery' } as unknown as ServerEvent;
    expect(applyEvent(initialCaptionState, unknown)).toBe(initialCaptionState);
  });
});

class FakeSocket implements WebSocketLike {
  static instances: FakeSocket[] = [];

  readyState = 0;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  sent: string[] = [];
  closedWith: number | undefined;
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(code?: number): void {
    this.closedWith = code;
    this.readyState = 3;
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  message(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as unknown as MessageEvent);
  }

  serverClose(code: number, reason = ''): void {
    this.readyState = 3;
    this.onclose?.({ code, reason } as unknown as CloseEvent);
  }
}

describe('connectCaptions', () => {
  const statuses: ConnectionState[] = [];
  const events: ServerEvent[] = [];

  function connect() {
    return connectCaptions({
      stageId: 'main',
      lang: 'es',
      baseUrl: 'ws://test',
      createSocket: (url) => new FakeSocket(url),
      random: () => 0,
      onEvent: (event) => events.push(event),
      onConnection: (state) => statuses.push(state),
    });
  }

  const last = (): ConnectionState | undefined => statuses[statuses.length - 1];

  beforeEach(() => {
    vi.useFakeTimers();
    FakeSocket.instances = [];
    statuses.length = 0;
    events.length = 0;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('builds the URL, reports live on open and forwards parsed events', () => {
    const connection = connect();
    const socket = FakeSocket.instances[0];
    expect(socket?.url).toBe('ws://test/ws/main?lang=es');
    expect(last()?.status).toBe('connecting');

    socket?.open();
    expect(last()?.status).toBe('live');

    socket?.message({ type: 'status', stage_id: 'main', state: 'LIVE', detail: null });
    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe('status');

    connection.close();
    expect(socket?.closedWith).toBe(1000);
  });

  it('reconnects with exponential backoff after an unexpected close', () => {
    connect();
    const first = FakeSocket.instances[0];
    first?.serverClose(1006);
    expect(last()?.status).toBe('reconnecting');
    expect(FakeSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(499);
    expect(FakeSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(2);

    // Never opened: the next delay doubles to 1000 ms.
    FakeSocket.instances[1]?.serverClose(1006);
    vi.advanceTimersByTime(999);
    expect(FakeSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(3);

    // A successful open resets the backoff.
    FakeSocket.instances[2]?.open();
    expect(last()?.status).toBe('live');
    FakeSocket.instances[2]?.serverClose(1001);
    vi.advanceTimersByTime(500);
    expect(FakeSocket.instances).toHaveLength(4);
  });

  it('caps the delay at 8 s', () => {
    connect();
    for (let i = 0; i < 6; i += 1) {
      FakeSocket.instances[i]?.serverClose(1006);
      vi.advanceTimersByTime(8000);
    }
    expect(FakeSocket.instances).toHaveLength(7);
  });

  it('stops and reports an error on fatal close codes', () => {
    connect();
    FakeSocket.instances[0]?.serverClose(4404, 'no such stage');
    expect(last()?.status).toBe('error');
    expect(last()?.message).toContain('unknown stage');
    vi.advanceTimersByTime(20000);
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it('sends a ping every 20 s while open and nothing else', () => {
    connect();
    const socket = FakeSocket.instances[0];
    socket?.open();
    vi.advanceTimersByTime(PING_INTERVAL_MS * 2);
    expect(socket?.sent).toEqual(['ping', 'ping']);
  });

  it('close() cancels a pending reconnect', () => {
    const connection = connect();
    FakeSocket.instances[0]?.serverClose(1006);
    connection.close();
    vi.advanceTimersByTime(20000);
    expect(FakeSocket.instances).toHaveLength(1);
  });
});
