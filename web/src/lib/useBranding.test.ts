// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { readableForeground } from './useBranding';

describe('readableForeground', () => {
  it('picks white text on dark brand colours', () => {
    expect(readableForeground('#2563eb')).toBe('#ffffff');
    expect(readableForeground('#7c3aed')).toBe('#ffffff');
    expect(readableForeground('#000000')).toBe('#ffffff');
  });

  it('picks black text on light brand colours', () => {
    expect(readableForeground('#facc15')).toBe('#000000');
    expect(readableForeground('#FFFFFF')).toBe('#000000');
  });

  it('returns null for anything that is not #RRGGBB', () => {
    expect(readableForeground('blue')).toBeNull();
    expect(readableForeground('#fff')).toBeNull();
    expect(readableForeground('rgb(0, 0, 0)')).toBeNull();
  });
});
