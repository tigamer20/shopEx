/**
 * Pure helpers behind the search session: default choices, approvals and derived totals.
 * Item indexes refer to positions in `SearchResponse.results` (same order as the request).
 */
import type { Offer, SearchResponse, Store } from '@/api/types';

/** Chosen offer per item index. */
export type OfferSelection = Record<number, Offer>;
/** Approval flag per item index. */
export type Approvals = Record<number, boolean>;

/** Indexes of the items that have at least one offer (only those can be approved). */
export function matchedIndexes(result: SearchResponse): number[] {
  return result.results.flatMap((item, index) => (item.best ? [index] : []));
}

/** Every matched item starts on its cheapest offer. */
export function defaultSelection(result: SearchResponse): OfferSelection {
  const selection: OfferSelection = {};
  result.results.forEach((item, index) => {
    if (item.best) {
      selection[index] = item.best;
    }
  });
  return selection;
}

/** The chosen offer for an item: the user's pick, else the cheapest one. */
export function chosenOffer(result: SearchResponse, selection: OfferSelection, index: number): Offer | null {
  return selection[index] ?? result.results[index]?.best ?? null;
}

/** True when there is at least one matched item and every matched item is approved. */
export function areAllApproved(result: SearchResponse | null, approved: Approvals): boolean {
  if (!result) {
    return false;
  }
  const indexes = matchedIndexes(result);
  return indexes.length > 0 && indexes.every((index) => approved[index] === true);
}

export function approveAllMatched(result: SearchResponse): Approvals {
  const approvals: Approvals = {};
  for (const index of matchedIndexes(result)) {
    approvals[index] = true;
  }
  return approvals;
}

/** Unique stores of the chosen offers, nearest first (unknown distances last). */
export function chosenStoresOf(result: SearchResponse | null, selection: OfferSelection): Store[] {
  if (!result) {
    return [];
  }
  const stores = new Map<number, Store>();
  for (const index of matchedIndexes(result)) {
    const offer = chosenOffer(result, selection, index);
    if (offer && !stores.has(offer.store.id)) {
      stores.set(offer.store.id, offer.store);
    }
  }
  return [...stores.values()].sort(
    (a, b) => (a.distance_km ?? Number.POSITIVE_INFINITY) - (b.distance_km ?? Number.POSITIVE_INFINITY),
  );
}

/** Σ chosen price × quantity, rounded to the cent. */
export function chosenTotalOf(result: SearchResponse | null, selection: OfferSelection): number {
  if (!result) {
    return 0;
  }
  const total = matchedIndexes(result).reduce((sum, index) => {
    const offer = chosenOffer(result, selection, index);
    const quantity = result.results[index]?.query.quantity ?? 1;
    return offer ? sum + offer.price * quantity : sum;
  }, 0);
  return Math.round(total * 100) / 100;
}
