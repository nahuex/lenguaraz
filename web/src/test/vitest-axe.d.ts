// SPDX-License-Identifier: Apache-2.0
// vitest-axe 0.1.0 types its matcher for the pre-1.0 `Vi` namespace; this declares it on
// the current `vitest` Matchers interface (same type parameters as vitest's own declaration).
import 'vitest';

declare module 'vitest' {
  interface Matchers<R extends void | Promise<void> = void | Promise<void>, T = unknown> {
    /** The axe-core results (from `axe()` in vitest-axe) contain no violation. */
    toHaveNoViolations(): R;
  }
}
