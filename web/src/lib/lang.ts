// SPDX-License-Identifier: Apache-2.0

/** A selectable caption language on a stage. */
export interface LanguageOption {
  /** Short code sent to the backend as `?lang=` (`es`, `en`, `pt`). */
  code: string;
  /** Human-readable label in English (falls back to the upper-cased code). */
  label: string;
  /** True when the language is one of the stage's source languages. */
  original: boolean;
}

/**
 * Derive the short language code from a BCP-47 tag: the primary subtag
 * before the first `-` (`en-US` -> `en`, `pt-BR` -> `pt`, `es` -> `es`).
 */
export function deriveShortCode(code: string): string {
  const trimmed = code.trim();
  const dash = trimmed.indexOf('-');
  const primary = dash === -1 ? trimmed : trimmed.slice(0, dash);
  return primary.toLowerCase();
}

/** English display name for a language code, e.g. `es` -> "Spanish". */
export function languageLabel(code: string): string {
  try {
    const names = new Intl.DisplayNames(['en'], { type: 'language' });
    const label = names.of(code);
    if (label && label.toLowerCase() !== code.toLowerCase()) {
      return label;
    }
  } catch {
    // Intl.DisplayNames unavailable or the code is not a valid tag.
  }
  return code.toUpperCase();
}

/**
 * Build the language picker options for a stage: the source languages first
 * (marked as original), then the translation targets, without duplicates.
 */
export function buildLanguageOptions(stage: {
  source_lang: string[];
  targets: string[];
}): LanguageOption[] {
  const seen = new Set<string>();
  const options: LanguageOption[] = [];
  for (const source of stage.source_lang) {
    const code = deriveShortCode(source);
    if (!code || seen.has(code)) continue;
    seen.add(code);
    options.push({ code, label: languageLabel(code), original: true });
  }
  for (const target of stage.targets) {
    const code = deriveShortCode(target);
    if (!code || seen.has(code)) continue;
    seen.add(code);
    options.push({ code, label: languageLabel(code), original: false });
  }
  return options;
}
