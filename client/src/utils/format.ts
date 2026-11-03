/**
 * Locale-aware formatting (prices are CAD; French uses fr-CA, English en-CA).
 * Every formatter returns "—" for a missing or non-finite value.
 */
import type { Language, UnitPriceUnit } from '@/api/types';
import { translate } from '@/i18n/translate';

export const MISSING_VALUE = '—';

export type IntlLocale = 'fr-CA' | 'en-CA';

export function intlLocale(language: Language): IntlLocale {
  return language === 'fr' ? 'fr-CA' : 'en-CA';
}

type Numeric = number | null | undefined;

function isNumber(value: Numeric): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function formatNumber(value: number, language: Language, maximumFractionDigits: number): string {
  return new Intl.NumberFormat(intlLocale(language), { maximumFractionDigits }).format(value);
}

/** `3.49` → "3,49 $" (fr) / "$3.49" (en). */
export function formatPrice(value: Numeric, language: Language): string {
  if (!isNumber(value)) {
    return MISSING_VALUE;
  }
  return new Intl.NumberFormat(intlLocale(language), { style: 'currency', currency: 'CAD' }).format(value);
}

/** Under 1 km in metres (nearest 10 m), under 10 km with one decimal, then whole kilometres. */
export function formatDistance(km: Numeric, language: Language): string {
  if (!isNumber(km) || km < 0) {
    return MISSING_VALUE;
  }
  if (km < 1) {
    const metres = Math.max(10, Math.round(km * 100) * 10);
    return metres >= 1000 ? `${formatNumber(1, language, 0)} km` : `${formatNumber(metres, language, 0)} m`;
  }
  return `${formatNumber(km, language, km < 10 ? 1 : 0)} km`;
}

/** `7` → "7 min"; `65` → "1 h 05" (fr) / "1 h 5 min" (en); under a minute → "< 1 min". */
export function formatDuration(minutes: Numeric, language: Language): string {
  if (!isNumber(minutes) || minutes < 0) {
    return MISSING_VALUE;
  }
  const total = Math.round(minutes);
  if (total < 1) {
    return '< 1 min';
  }
  if (total < 60) {
    return `${total} min`;
  }
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (rest === 0) {
    return `${hours} h`;
  }
  return language === 'fr' ? `${hours} h ${String(rest).padStart(2, '0')}` : `${hours} h ${rest} min`;
}

const UNIT_SUFFIX_KEYS = {
  kg: 'common.units.per_kg',
  L: 'common.units.per_l',
  unit: 'common.units.per_unit',
} as const satisfies Record<UnitPriceUnit, string>;

/** `12.5, "kg"` → "12,50 $/kg" (fr) / "$12.50/kg" (en). */
export function formatUnitPrice(value: Numeric, unit: UnitPriceUnit, language: Language): string {
  if (!isNumber(value)) {
    return MISSING_VALUE;
  }
  return `${formatPrice(value, language)}${translate(language, UNIT_SUFFIX_KEYS[unit])}`;
}

/** ISO date-time → localised calendar date, e.g. "2 nov. 2026" / "Nov 2, 2026". */
export function formatDate(iso: string | null | undefined, language: Language): string {
  const date = iso ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime())) {
    return MISSING_VALUE;
  }
  return new Intl.DateTimeFormat(intlLocale(language), {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
}
