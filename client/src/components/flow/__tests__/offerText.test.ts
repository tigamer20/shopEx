import type { ItemResult, Offer, Product, SearchResponse, Store } from '@/api/types';

import { formatSize, productName, purchasesByStore, storeAddress } from '../offerText';

function store(id: number): Store {
  return {
    id,
    name: `Store ${id}`,
    chain: null,
    address: null,
    lat: 45.5,
    lon: -73.5,
    distance_km: id,
    source: 'demo',
    price_tier: 'standard',
  };
}

function product(id: number, overrides: Partial<Product> = {}): Product {
  return {
    id,
    slug: `p-${id}`,
    name_fr: `Produit ${id}`,
    name_en: `Product ${id}`,
    brand: 'Fermette',
    section_id: 'dairy',
    size_value: 1,
    size_unit: 'L',
    tags: [],
    ...overrides,
  };
}

function offer(priceId: number, storeId: number, productId = priceId): Offer {
  return {
    price_id: priceId,
    product: product(productId),
    store: store(storeId),
    price: 2,
    regular_price: 2,
    on_sale: false,
    unit_price: 2,
    unit_price_unit: 'L',
    updated_at: '2026-11-02T00:00:00Z',
    source: 'demo',
  };
}

function item(best: Offer | null, quantity = 1, alternatives: Offer[] = []): ItemResult {
  return {
    query: { name: 'x', brand: null, quantity },
    matched: best !== null,
    brand_matched: null,
    best,
    alternatives,
    line_total: best ? best.price * quantity : null,
    message_key: best ? null : 'search.no_match',
  };
}

describe('productName / formatSize', () => {
  it('uses the current language', () => {
    expect(productName(product(1), 'fr')).toBe('Produit 1');
    expect(productName(product(1), 'en')).toBe('Product 1');
  });

  it('formats sizes per locale and unit', () => {
    expect(formatSize({ size_value: 1.5, size_unit: 'L' }, 'fr')).toBe('1,5 L');
    expect(formatSize({ size_value: 1.5, size_unit: 'L' }, 'en')).toBe('1.5 L');
    expect(formatSize({ size_value: 500, size_unit: 'g' }, 'en')).toBe('500 g');
    expect(formatSize({ size_value: 12, size_unit: 'unit' }, 'en')).toBe('12 unit(s)');
  });
});

describe('purchasesByStore', () => {
  it('groups chosen offers by store and skips unmatched items', () => {
    const alternative = offer(30, 2, 3);
    const result: SearchResponse = {
      list_id: 1,
      prices_are_demo: true,
      currency: 'CAD',
      results: [item(offer(10, 1, 1), 2), item(null), item(offer(20, 1, 2), 1, [alternative])],
      stores: [store(1)],
      best_total: 6,
    };
    const grouped = purchasesByStore(result, { 2: alternative }, 'en');
    expect(grouped.get(1)).toEqual([{ itemIndex: 0, name: 'Product 1', quantity: 2 }]);
    expect(grouped.get(2)).toEqual([{ itemIndex: 2, name: 'Product 3', quantity: 1 }]);
    expect(grouped.size).toBe(2);
  });
});

describe('storeAddress', () => {
  it('shows the OSM address as is, or null when unknown', () => {
    expect(storeAddress({ source: 'osm', address: '12 Rue Exemple, Ville' }, 'en')).toBe('12 Rue Exemple, Ville');
    expect(storeAddress({ source: 'osm', address: null }, 'fr')).toBeNull();
  });

  it('labels demo stores in the UI language instead of the server placeholder', () => {
    const demo = { source: 'demo', address: 'Magasin de démonstration, emplacement fictif' } as const;
    expect(storeAddress(demo, 'en')).toBe('Demo store, fictional location');
    expect(storeAddress(demo, 'fr')).toBe('Magasin de démonstration, emplacement fictif');
  });
});
