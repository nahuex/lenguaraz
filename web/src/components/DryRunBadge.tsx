// SPDX-License-Identifier: Apache-2.0
import { FlaskConical } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

/** Shown whenever any stage runs on the fake engine (no credentials). */
export function DryRunBadge() {
  return (
    <Badge variant="secondary" role="status" className="max-w-full font-semibold">
      <FlaskConical aria-hidden="true" data-icon="inline-start" />
      Dry run · simulated captions, no API key
    </Badge>
  );
}
