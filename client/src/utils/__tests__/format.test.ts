import {
  formatDate,
  formatDistance,
  formatDuration,
  formatPrice,
  formatUnitPrice,
  intlLocale,
  MISSING_VALUE,
} from '../format';

/** Intl uses (narrow) no-break spaces in fr-CA; compare with plain spaces. */
const plain = (text: string): string => text.replace(/\s/g, ' ');

describe('intlLocale', () => {
  it('uses Canadian locales', () => {
    expect(intlLocale('fr')).toBe('fr-CA');
    expect(intlLocale('en')).toBe('en-CA');
  });
});

describe('formatPrice', () => {
  it('formats CAD per language', () => {
    expect(plain(formatPrice(3.49, 'fr'))).toBe('3,49 $');
    expect(formatPrice(3.49, 'en')).toBe('$3.49');
    expect(plain(formatPrice(1234.5, 'fr'))).toBe('1 234,50 $');
    expect(formatPrice(1234.5, 'en')).toBe('$1,234.50');
  });

  it('returns a dash for missing values', () => {
    expect(formatPrice(null, 'fr')).toBe(MISSING_VALUE);
    expect(formatPrice(Number.NaN, 'en')).toBe(MISSING_VALUE);
  });
});

describe('formatDistance', () => {
  it('uses metres under 1 km, rounded to 10 m', () => {
    expect(formatDistance(0.853, 'en')).toBe('850 m');
    expect(formatDistance(0.001, 'fr')).toBe('10 m');
    expect(formatDistance(0.998, 'en')).toBe('1 km');
  });

  it('uses one decimal under 10 km with the local separator', () => {
    expect(formatDistance(2.44, 'fr')).toBe('2,4 km');
    expect(formatDistance(2.44, 'en')).toBe('2.4 km');
  });

  it('uses whole kilometres from 10 km', () => {
    expect(formatDistance(12.6, 'en')).toBe('13 km');
  });

  it('returns a dash for missing or negative values', () => {
    expect(formatDistance(null, 'en')).toBe(MISSING_VALUE);
    expect(formatDistance(-1, 'en')).toBe(MISSING_VALUE);
  });
});

describe('formatDuration', () => {
  it('formats minutes and hours', () => {
    expect(formatDuration(0.4, 'en')).toBe('< 1 min');
    expect(formatDuration(7.2, 'fr')).toBe('7 min');
    expect(formatDuration(65, 'fr')).toBe('1 h 05');
    expect(formatDuration(65, 'en')).toBe('1 h 5 min');
    expect(formatDuration(120, 'en')).toBe('2 h');
  });

  it('returns a dash for missing values', () => {
    expect(formatDuration(undefined, 'fr')).toBe(MISSING_VALUE);
  });
});

describe('formatUnitPrice', () => {
  it('appends the localised unit', () => {
    expect(plain(formatUnitPrice(12.5, 'kg', 'fr'))).toBe('12,50 $/kg');
    expect(formatUnitPrice(2, 'L', 'en')).toBe('$2.00/L');
    expect(plain(formatUnitPrice(0.99, 'unit', 'fr'))).toBe('0,99 $/unité');
    expect(formatUnitPrice(0.99, 'unit', 'en')).toBe('$0.99/unit');
  });

  it('returns a dash for missing values', () => {
    expect(formatUnitPrice(null, 'kg', 'en')).toBe(MISSING_VALUE);
  });
});

describe('formatDate', () => {
  it('formats a calendar date per language', () => {
    // Midday UTC keeps the same calendar day in every Canadian time zone.
    expect(formatDate('2026-11-02T12:00:00Z', 'en')).toContain('2026');
    expect(formatDate('2026-11-02T12:00:00Z', 'fr')).toContain('nov');
  });

  it('returns a dash for missing or invalid dates', () => {
    expect(formatDate(null, 'en')).toBe(MISSING_VALUE);
    expect(formatDate('not a date', 'fr')).toBe(MISSING_VALUE);
  });
});
