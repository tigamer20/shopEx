/**
 * Pure translation helpers (no React): used by the I18nProvider, the formatters and tests.
 */
import type { Language } from '@/api/types';

import en from './locales/en';
import fr from './locales/fr';
import type { Dictionary, TranslationKey, TranslationParams } from './types';

export const DEFAULT_LANGUAGE: Language = 'fr';

export const dictionaries: Record<Language, Dictionary> = { fr, en };

/** Walks a dotted key through a dictionary; only own properties count. */
function lookup(dictionary: Dictionary, key: string): string | undefined {
  let node: unknown = dictionary;
  for (const part of key.split('.')) {
    if (node === null || typeof node !== 'object' || !Object.prototype.hasOwnProperty.call(node, part)) {
      return undefined;
    }
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === 'string' ? node : undefined;
}

/** Replaces `{name}` placeholders; unknown placeholders are left untouched. */
export function interpolate(template: string, params: TranslationParams): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match,
  );
}

/** Translates `key`, falling back to French, then to the key itself. */
export function translate(language: Language, key: TranslationKey, params?: TranslationParams): string {
  const template = lookup(dictionaries[language], key) ?? lookup(dictionaries.fr, key) ?? key;
  return params ? interpolate(template, params) : template;
}

/** Narrows a server-provided string (e.g. `ItemResult.message_key`) to a known key. */
export function isTranslationKey(key: string): key is TranslationKey {
  return lookup(dictionaries.fr, key) !== undefined;
}

/** Maps a BCP-47 tag or language code (`"fr-CA"`, `"en"`) to a supported language. */
export function toLanguage(tag: string | null | undefined): Language | null {
  const code = (tag ?? '').trim().slice(0, 2).toLowerCase();
  return code === 'fr' || code === 'en' ? code : null;
}
