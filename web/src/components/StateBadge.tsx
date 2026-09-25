// SPDX-License-Identifier: Apache-2.0
import type { ComponentProps } from 'react';
import { Badge } from '@/components/ui/badge';
import type { StageState } from '../lib/api';

type BadgeVariant = NonNullable<ComponentProps<typeof Badge>['variant']>;

/**
 * Badge variant per stage state. LIVE is the one highlighted state (primary, i.e. the brand
 * colour); DEGRADED warns; STARTING and ROTATING are transitional; IDLE and STOPPED stay
 * quiet. The state word is always rendered, so colour is never the only cue.
 */
const VARIANTS: Record<StageState, BadgeVariant> = {
  LIVE: 'default',
  STARTING: 'secondary',
  ROTATING: 'secondary',
  DEGRADED: 'destructive',
  IDLE: 'outline',
  STOPPED: 'outline',
};

interface StateBadgeProps {
  state: StageState;
}

export function StateBadge({ state }: StateBadgeProps) {
  return (
    <Badge
      variant={VARIANTS[state] ?? 'outline'}
      data-state={state}
      className="font-semibold tracking-wide"
    >
      {state}
    </Badge>
  );
}
