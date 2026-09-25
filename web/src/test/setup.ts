// SPDX-License-Identifier: Apache-2.0
import '@testing-library/jest-dom/vitest';
import * as axeMatchers from 'vitest-axe/matchers';
import { afterEach, expect } from 'vitest';
import { cleanup } from '@testing-library/react';

// `expect(await axe(container)).toHaveNoViolations()` — types in src/test/vitest-axe.d.ts.
expect.extend(axeMatchers);

afterEach(() => {
  cleanup();
});
