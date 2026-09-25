// SPDX-License-Identifier: Apache-2.0
// Derived from shadcn/ui (https://ui.shadcn.com) — MIT License, Copyright (c) 2023 shadcn
import * as React from 'react';
import { cn } from 'cn';
import { Separator as SeparatorPrimitive } from 'radix-ui';

function Separator({
  className,
  orientation = 'horizontal',
  decorative = true,
  ...props
}: React.ComponentProps<typeof SeparatorPrimitive.Root>) {
  return (
    <SeparatorPrimitive.Root
      data-slot="separator"
      decorative={decorative}
      orientation={orientation}
      className={cn(
        'shrink-0 bg-border data-horizontal:h-px data-horizontal:w-full data-vertical:w-px data-vertical:self-stretch',
        className,
      )}
      {...props}
    />
  );
}

export { Separator };
