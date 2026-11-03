import type { GroceryItemInput } from '@/api/types';

import { addItem, clampQuantity, makeItem, MAX_ITEMS, moveItem, removeItemAt, setQuantityAt } from '../listItems';

const milk: GroceryItemInput = { name: 'Lait', brand: null, quantity: 1 };
const eggs: GroceryItemInput = { name: 'Œufs', brand: 'Fermette', quantity: 2 };
const bread: GroceryItemInput = { name: 'Pain', brand: null, quantity: 1 };

describe('makeItem', () => {
  it('cleans the input and clamps the quantity', () => {
    expect(makeItem('  lait   2 %  ', '  ', 0)).toEqual({ name: 'lait 2 %', brand: null, quantity: 1 });
    expect(makeItem('Café', ' Brûlerie ', 150)).toEqual({ name: 'Café', brand: 'Brûlerie', quantity: 99 });
    expect(makeItem('   ', 'x', 1)).toBeNull();
  });

  it('truncates to the API limits', () => {
    const item = makeItem('a'.repeat(150), 'b'.repeat(80), 1);
    expect(item?.name).toHaveLength(100);
    expect(item?.brand).toHaveLength(60);
  });
});

describe('clampQuantity', () => {
  it('keeps 1..99 integers', () => {
    expect(clampQuantity(5)).toBe(5);
    expect(clampQuantity(2.6)).toBe(3);
    expect(clampQuantity(-1)).toBe(1);
    expect(clampQuantity(100)).toBe(99);
    expect(clampQuantity(Number.NaN)).toBe(1);
  });
});

describe('addItem', () => {
  it('appends a new item', () => {
    expect(addItem([milk], bread)).toEqual({ items: [milk, bread], outcome: 'added' });
  });

  it('merges the same name and brand, ignoring case and accents', () => {
    const result = addItem([milk, eggs], { name: 'oeufs', brand: 'FERMETTE', quantity: 3 });
    expect(result.outcome).toBe('merged');
    expect(result.items[1]).toEqual({ ...eggs, quantity: 5 });
  });

  it('keeps different brands apart', () => {
    expect(addItem([eggs], { name: 'Œufs', brand: null, quantity: 1 }).outcome).toBe('added');
  });

  it('refuses a new line past the maximum but still merges', () => {
    const full = Array.from({ length: MAX_ITEMS }, (_, index) => ({ name: `item ${index}`, brand: null, quantity: 1 }));
    expect(addItem(full, bread).outcome).toBe('full');
    expect(addItem(full, { name: 'ITEM 0', brand: null, quantity: 1 }).outcome).toBe('merged');
  });
});

describe('list edits', () => {
  it('removes, sets quantities and moves items', () => {
    expect(removeItemAt([milk, eggs, bread], 1)).toEqual([milk, bread]);
    expect(setQuantityAt([milk, eggs], 0, 120)).toEqual([{ ...milk, quantity: 99 }, eggs]);
    expect(moveItem([milk, eggs, bread], 2, -1)).toEqual([milk, bread, eggs]);
    expect(moveItem([milk, eggs, bread], 0, 1)).toEqual([eggs, milk, bread]);
    expect(moveItem([milk, eggs], 0, -1)).toEqual([milk, eggs]);
    expect(moveItem([milk, eggs], 1, 1)).toEqual([milk, eggs]);
  });
});
