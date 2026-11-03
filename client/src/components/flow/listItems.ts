/**
 * Pure helpers for the list editor. Limits mirror `GroceryItemInput` (§4):
 * name 1..100 chars, brand ≤ 60 chars, quantity 1..99, at most 100 items per list.
 */
import type { GroceryItemInput } from '@/api/types';

export const MAX_ITEMS = 100;
export const MAX_NAME_LENGTH = 100;
export const MAX_BRAND_LENGTH = 60;
export const MAX_LIST_NAME_LENGTH = 80;
export const MIN_QUANTITY = 1;
export const MAX_QUANTITY = 99;

export function clampQuantity(quantity: number): number {
  if (!Number.isFinite(quantity)) {
    return MIN_QUANTITY;
  }
  return Math.min(MAX_QUANTITY, Math.max(MIN_QUANTITY, Math.round(quantity)));
}

/** Collapses whitespace and trims. */
export function cleanText(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/** Comparison key: case- and accent-insensitive. */
function matchKey(text: string | null): string {
  return cleanText(text ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/œ/g, 'oe')
    .replace(/æ/g, 'ae');
}

/** Builds a valid item from form input, or null when the name is blank. */
export function makeItem(name: string, brand: string | null, quantity: number): GroceryItemInput | null {
  const cleanName = cleanText(name).slice(0, MAX_NAME_LENGTH);
  if (!cleanName) {
    return null;
  }
  const cleanBrand = cleanText(brand ?? '').slice(0, MAX_BRAND_LENGTH);
  return { name: cleanName, brand: cleanBrand || null, quantity: clampQuantity(quantity) };
}

export type AddItemOutcome = 'added' | 'merged' | 'full';

/**
 * Adds an item; the same name + brand (ignoring case and accents) bumps the existing quantity
 * instead of creating a duplicate line.
 */
export function addItem(
  items: readonly GroceryItemInput[],
  item: GroceryItemInput,
): { items: GroceryItemInput[]; outcome: AddItemOutcome } {
  const index = items.findIndex(
    (existing) => matchKey(existing.name) === matchKey(item.name) && matchKey(existing.brand) === matchKey(item.brand),
  );
  if (index >= 0) {
    const next = items.map((existing, position) =>
      position === index ? { ...existing, quantity: clampQuantity(existing.quantity + item.quantity) } : existing,
    );
    return { items: next, outcome: 'merged' };
  }
  if (items.length >= MAX_ITEMS) {
    return { items: [...items], outcome: 'full' };
  }
  return { items: [...items, item], outcome: 'added' };
}

export function removeItemAt(items: readonly GroceryItemInput[], index: number): GroceryItemInput[] {
  return items.filter((_, position) => position !== index);
}

export function setQuantityAt(items: readonly GroceryItemInput[], index: number, quantity: number): GroceryItemInput[] {
  return items.map((item, position) => (position === index ? { ...item, quantity: clampQuantity(quantity) } : item));
}

/** Moves the item at `from` by `delta` positions (out-of-range moves are ignored). */
export function moveItem(items: readonly GroceryItemInput[], from: number, delta: number): GroceryItemInput[] {
  const to = from + delta;
  if (from < 0 || from >= items.length || to < 0 || to >= items.length) {
    return [...items];
  }
  const next = [...items];
  const [moved] = next.splice(from, 1);
  if (moved) {
    next.splice(to, 0, moved);
  }
  return next;
}
