import type { ItemResult, Offer, SearchResponse, Store } from '@/api/types';

import {
  approveAllMatched,
  areAllApproved,
  chosenStoresOf,
  chosenTotalOf,
  defaultSelection,
  matchedIndexes,
} from '../selection';

function store(id: number, distance_km: number | null): Store {
  return {
    id,
    name: `Store ${id}`,
    chain: null,
    address: null,
    lat: 45.5,
    lon: -73.6,
    distance_km,
    source: 'demo',
    price_tier: 'standard',
  };
}

function offer(price_id: number, price: number, offerStore: Store): Offer {
  return {
    price_id,
    product: {
      id: price_id,
      slug: `product-${price_id}`,
      name_fr: 'Produit',
      name_en: 'Product',
      brand: 'Fictional Farms',
      section_id: 'pantry',
      size_value: 1,
      size_unit: 'unit',
      tags: [],
    },
    store: offerStore,
    price,
    regular_price: price,
    on_sale: false,
    unit_price: price,
    unit_price_unit: 'unit',
    updated_at: '2026-11-02T12:00:00Z',
    source: 'demo',
  };
}

function item(best: Offer | null, quantity: number, alternatives: Offer[] = []): ItemResult {
  return {
    query: { name: 'item', brand: null, quantity },
    matched: best !== null,
    brand_matched: null,
    best,
    alternatives,
    line_total: best ? best.price * quantity : null,
    message_key: best ? null : 'search.no_match',
  };
}

const near = store(1, 0.8);
const far = store(2, 3.2);
const unknown = store(3, null);

const cheapMilk = offer(10, 2.5, far);
const otherMilk = offer(11, 2.75, near);
const bread = offer(20, 3.1, near);

const result: SearchResponse = {
  list_id: 7,
  prices_are_demo: true,
  currency: 'CAD',
  results: [item(cheapMilk, 2, [otherMilk]), item(null, 1), item(bread, 1)],
  stores: [near, far],
  best_total: 8.1,
};

describe('search selection', () => {
  it('lists matched items only', () => {
    expect(matchedIndexes(result)).toEqual([0, 2]);
  });

  it('defaults every matched item to its best offer', () => {
    expect(defaultSelection(result)).toEqual({ 0: cheapMilk, 2: bread });
  });

  it('requires every matched item to be approved', () => {
    expect(areAllApproved(null, {})).toBe(false);
    expect(areAllApproved(result, { 0: true })).toBe(false);
    expect(areAllApproved(result, { 0: true, 2: true })).toBe(true);
    expect(areAllApproved(result, approveAllMatched(result))).toBe(true);
  });

  it('is never "all approved" without any match', () => {
    const empty: SearchResponse = { ...result, results: [item(null, 1)] };
    expect(areAllApproved(empty, approveAllMatched(empty))).toBe(false);
  });

  it('computes the total from the chosen offers and quantities', () => {
    expect(chosenTotalOf(result, defaultSelection(result))).toBe(8.1);
    expect(chosenTotalOf(result, { ...defaultSelection(result), 0: otherMilk })).toBe(8.6);
    expect(chosenTotalOf(null, {})).toBe(0);
  });

  it('returns the unique chosen stores, nearest first', () => {
    expect(chosenStoresOf(result, defaultSelection(result)).map((s) => s.id)).toEqual([1, 2]);
    expect(chosenStoresOf(result, { 0: otherMilk, 2: bread }).map((s) => s.id)).toEqual([1]);
    expect(chosenStoresOf(result, { 0: offer(12, 1, unknown) }).map((s) => s.id)).toEqual([1, 3]);
  });
});
