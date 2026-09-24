// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { buildLanguageOptions, deriveShortCode, languageLabel } from './lang';

describe('deriveShortCode', () => {
  it('returns the primary subtag of a BCP-47 tag', () => {
    expect(deriveShortCode('en-US')).toBe('en');
    expect(deriveShortCode('pt-BR')).toBe('pt');
    expect(deriveShortCode('es')).toBe('es');
    expect(deriveShortCode(' ES-419 ')).toBe('es');
  });
});

describe('languageLabel', () => {
  it('names known languages in English and falls back to the code', () => {
    expect(languageLabel('es')).toBe('Spanish');
    expect(languageLabel('zz')).toBe('ZZ');
  });
});

describe('buildLanguageOptions', () => {
  it('lists sources first as original and deduplicates targets', () => {
    const options = buildLanguageOptions({ source_lang: ['en-US'], targets: ['es', 'en'] });
    expect(options.map((o) => o.code)).toEqual(['en', 'es']);
    expect(options[0]?.original).toBe(true);
    expect(options[1]?.original).toBe(false);
  });
});
