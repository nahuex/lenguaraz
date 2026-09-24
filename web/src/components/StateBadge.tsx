// SPDX-License-Identifier: Apache-2.0
import type { StageState } from '../lib/api';

/**
 * Solid badge per stage state. Each background/text pair keeps >= 4.5:1
 * contrast on its own, so the badge reads the same in every theme.
 */
const STYLES: Record<StageState, string> = {
  LIVE: 'bg-[#22c55e] text-[#052e16]',
  STARTING: 'bg-[#f59e0b] text-[#451a03]',
  ROTATING: 'bg-[#f59e0b] text-[#451a03]',
  DEGRADED: 'bg-[#f97316] text-[#431407]',
  IDLE: 'bg-[#9ca3af] text-[#111827]',
  STOPPED: 'bg-[#9ca3af] text-[#111827]',
};

interface StateBadgeProps {
  state: StageState;
}

export function StateBadge({ state }: StateBadgeProps) {
  const style = STYLES[state] ?? STYLES.IDLE;
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide ${style}`}
      data-state={state}
    >
      {state}
    </span>
  );
}
