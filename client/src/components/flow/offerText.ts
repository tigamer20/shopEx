/**
 * Text helpers for products and offers (localised names, sizes, purchases per store).
 */
import type { Language, Offer, Product, SearchResponse, Store } from '@/api/types';
import { translate } from '@/i18n/translate';
import { chosenOffer, matchedIndexes, type OfferSelection } from '@/search/selection';

export function productName(product: Product, language: Language): string {
  return language === 'fr' ? product.name_fr : product.name_en;
}

/** `500 g`, `1,5 L` (fr) / `1.5 L` (en), `12 unit(s)`. */
export function formatSize(product: Pick<Product, 'size_value' | 'size_unit'>, language: Language): string {
  const value = new Intl.NumberFormat(language === 'fr' ? 'fr-CA' : 'en-CA', { maximumFractionDigits: 2 }).format(
    product.size_value,
  );
  if (product.size_unit === 'unit') {
    return translate(language, 'search.offer.unit_count', { count: value });
  }
  return `${value} ${product.size_unit}`;
}

/**
 * Address line of a store. Demo stores carry a French placeholder address from the server, so
 * they get a translated label instead; OSM addresses are shown as they are (null when unknown).
 */
export function storeAddress(store: Pick<Store, 'source' | 'address'>, language: Language): string | null {
  return store.source === 'demo' ? translate(language, 'itinerary.demo_store_address') : store.address;
}

export interface Purchase {
  itemIndex: number;
  name: string;
  quantity: number;
}

/** What to buy in each store: the chosen offers of matched items, grouped by store id. */
export function purchasesByStore(
  result: SearchResponse,
  selection: OfferSelection,
  language: Language,
): Map<number, Purchase[]> {
  const byStore = new Map<number, Purchase[]>();
  for (const index of matchedIndexes(result)) {
    const offer: Offer | null = chosenOffer(result, selection, index);
    if (!offer) {
      continue;
    }
    const purchases = byStore.get(offer.store.id) ?? [];
    purchases.push({
      itemIndex: index,
      name: productName(offer.product, language),
      quantity: result.results[index]?.query.quantity ?? 1,
    });
    byStore.set(offer.store.id, purchases);
  }
  return byStore;
}
