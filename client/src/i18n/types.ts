import type fr from './locales/fr';

/** Shape of a full dictionary, derived from the French (reference) locale. */
export type Dictionary = typeof fr;

/** Dotted paths to every string leaf, e.g. `"results.see_more"`. */
type LeafPaths<T> = {
  [K in keyof T & string]: T[K] extends string
    ? K
    : T[K] extends Record<string, unknown>
      ? `${K}.${LeafPaths<T[K]>}`
      : never;
}[keyof T & string];

export type TranslationKey = LeafPaths<Dictionary>;

/** Values for `{param}` placeholders. */
export type TranslationParams = Record<string, string | number>;

export type Translate = (key: TranslationKey, params?: TranslationParams) => string;
