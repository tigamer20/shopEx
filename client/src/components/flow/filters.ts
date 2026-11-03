/**
 * Browse filters (ARCHITECTURE §5 "Browse"): pure state helpers and the mapping to
 * `GET /catalog/offers` query parameters.
 */
import type { DietaryTag, OffersQuery, SortBy } from '@/api/types';

export interface BrowseFilters {
  minPrice: number | null;
  maxPrice: number | null;
  /** Free text, '' = any brand. */
  brand: string;
  /** Free text, '' = any chain. */
  chain: string;
  tags: DietaryTag[];
  onSaleOnly: boolean;
  /** null = the user's default search radius. */
  radiusKm: number | null;
  sort: SortBy;
}

export const EMPTY_FILTERS: BrowseFilters = {
  minPrice: null,
  maxPrice: null,
  brand: '',
  chain: '',
  tags: [],
  onSaleOnly: false,
  radiusKm: null,
  sort: 'price',
};

/** Radius choices offered in the filter sheet (km, within the server's 1..50 limit). */
export const RADIUS_CHOICES: readonly number[] = [2, 5, 10, 20, 50];

/** Offers fetched per page (`limit`, 1..100 server-side). */
export const OFFERS_PAGE_SIZE = 30;

const PRICE_PATTERN = /^\d{1,5}([.,]\d{1,2})?$/;

/**
 * Parses a price typed by the user ("4,99", "4.99", " 12 "): '' → null (no bound),
 * malformed → 'invalid'.
 */
export function parsePriceInput(text: string): number | null | 'invalid' {
  const trimmed = text.trim().replace(/\s|\$/g, '');
  if (!trimmed) {
    return null;
  }
  if (!PRICE_PATTERN.test(trimmed)) {
    return 'invalid';
  }
  return Number(trimmed.replace(',', '.'));
}

/** Shows a stored bound back in the text field (French uses a decimal comma). */
export function priceToInput(value: number | null, language: 'fr' | 'en'): string {
  if (value === null) {
    return '';
  }
  const text = Number.isInteger(value) ? String(value) : value.toFixed(2);
  return language === 'fr' ? text.replace('.', ',') : text;
}

export function isPriceRangeValid(filters: Pick<BrowseFilters, 'minPrice' | 'maxPrice'>): boolean {
  return filters.minPrice === null || filters.maxPrice === null || filters.minPrice <= filters.maxPrice;
}

export function toggleTag(tags: readonly DietaryTag[], tag: DietaryTag): DietaryTag[] {
  return tags.includes(tag) ? tags.filter((value) => value !== tag) : [...tags, tag];
}

/** Number of filters differing from the defaults (shown on the "Filters" button). */
export function countActiveFilters(filters: BrowseFilters): number {
  let count = 0;
  if (filters.minPrice !== null || filters.maxPrice !== null) count += 1;
  if (filters.brand.trim()) count += 1;
  if (filters.chain.trim()) count += 1;
  count += filters.tags.length;
  if (filters.onSaleOnly) count += 1;
  if (filters.radiusKm !== null) count += 1;
  if (filters.sort !== EMPTY_FILTERS.sort) count += 1;
  return count;
}

export interface OffersQueryContext {
  lat: number;
  lon: number;
  /** Search text (already debounced). */
  q: string;
  /** Section id, null = every section. */
  section: string | null;
  /** The user's default radius, used when no radius filter is set. */
  defaultRadiusKm?: number;
  offset?: number;
}

/** Builds the `GET /catalog/offers` query; empty values are omitted. */
export function toOffersQuery(filters: BrowseFilters, context: OffersQueryContext): OffersQuery {
  const query: OffersQuery = {
    lat: context.lat,
    lon: context.lon,
    sort: filters.sort,
    limit: OFFERS_PAGE_SIZE,
    offset: context.offset ?? 0,
  };
  const radius = filters.radiusKm ?? context.defaultRadiusKm;
  if (radius !== undefined) query.radius_km = radius;
  const q = context.q.trim();
  if (q) query.q = q;
  if (context.section) query.section = context.section;
  const brand = filters.brand.trim();
  if (brand) query.brand = brand;
  const chain = filters.chain.trim();
  if (chain) query.chain = chain;
  if (filters.tags.length > 0) query.tags = [...filters.tags];
  if (filters.onSaleOnly) query.on_sale = true;
  if (filters.minPrice !== null) query.min_price = filters.minPrice;
  if (filters.maxPrice !== null) query.max_price = filters.maxPrice;
  return query;
}
