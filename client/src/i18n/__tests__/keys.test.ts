import en from '../locales/en';
import fr from '../locales/fr';
import { interpolate, isTranslationKey, toLanguage, translate } from '../translate';

/** Flattens a nested dictionary into `{ "a.b.c": "text" }`. */
function flatten(node: unknown, prefix = ''): Record<string, unknown> {
  if (node === null || typeof node !== 'object') {
    return { [prefix]: node };
  }
  return Object.entries(node as Record<string, unknown>).reduce<Record<string, unknown>>(
    (entries, [key, value]) => ({ ...entries, ...flatten(value, prefix ? `${prefix}.${key}` : key) }),
    {},
  );
}

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1] ?? '').sort();
}

const frEntries = flatten(fr);
const enEntries = flatten(en);

describe('locale parity', () => {
  it('fr and en have exactly the same keys', () => {
    expect(Object.keys(enEntries).sort()).toEqual(Object.keys(frEntries).sort());
  });

  it('every value is a non-empty string', () => {
    for (const entries of [frEntries, enEntries]) {
      for (const [key, value] of Object.entries(entries)) {
        expect({ key, type: typeof value }).toEqual({ key, type: 'string' });
        expect({ key, empty: (value as string).trim() === '' }).toEqual({ key, empty: false });
      }
    }
  });

  it('fr and en use the same {placeholders}', () => {
    for (const [key, value] of Object.entries(frEntries)) {
      expect({ key, params: placeholders(String(enEntries[key])) }).toEqual({
        key,
        params: placeholders(String(value)),
      });
    }
  });

  it('defines the message keys the search API can return', () => {
    expect(isTranslationKey('search.no_match')).toBe(true);
    expect(isTranslationKey('search.brand_not_found')).toBe(true);
  });

  it('keeps the brand name and slogan identical in both languages', () => {
    expect(en.common.app_name).toBe('ShopEx');
    expect(fr.common.app_name).toBe('ShopEx');
    expect(en.common.slogan).toBe('Eat smarter & shop master');
    expect(fr.common.slogan).toBe('Eat smarter & shop master');
  });
});

describe('translate', () => {
  it('returns the string for the requested language', () => {
    expect(translate('fr', 'common.tabs.home')).toBe('Accueil');
    expect(translate('en', 'common.tabs.home')).toBe('Home');
  });

  it('interpolates {params}', () => {
    expect(translate('en', 'home.greeting', { name: 'Alex' })).toBe('Hi Alex!');
    expect(interpolate('{a} + {a} = {b}', { a: 1, b: 2 })).toBe('1 + 1 = 2');
  });

  it('leaves unknown placeholders untouched', () => {
    expect(interpolate('Hello {name}', {})).toBe('Hello {name}');
  });

  it('rejects unknown keys and inherited properties', () => {
    expect(isTranslationKey('nope.missing')).toBe(false);
    expect(isTranslationKey('common')).toBe(false);
    expect(isTranslationKey('common.constructor')).toBe(false);
    expect(isTranslationKey('__proto__.toString')).toBe(false);
  });
});

describe('toLanguage', () => {
  it('maps locale tags to supported languages', () => {
    expect(toLanguage('fr-CA')).toBe('fr');
    expect(toLanguage('EN')).toBe('en');
    expect(toLanguage('de-DE')).toBeNull();
    expect(toLanguage(null)).toBeNull();
  });
});
