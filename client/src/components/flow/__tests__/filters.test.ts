import {
  countActiveFilters,
  EMPTY_FILTERS,
  isPriceRangeValid,
  OFFERS_PAGE_SIZE,
  parsePriceInput,
  priceToInput,
  toggleTag,
  toOffersQuery,
} from '../filters';

describe('parsePriceInput', () => {
  it('accepts comma or dot decimals and blanks', () => {
    expect(parsePriceInput('4,99')).toBe(4.99);
    expect(parsePriceInput(' 4.5 ')).toBe(4.5);
    expect(parsePriceInput('12')).toBe(12);
    expect(parsePriceInput('3 $')).toBe(3);
    expect(parsePriceInput('')).toBeNull();
    expect(parsePriceInput('   ')).toBeNull();
  });

  it('flags malformed values', () => {
    expect(parsePriceInput('abc')).toBe('invalid');
    expect(parsePriceInput('-2')).toBe('invalid');
    expect(parsePriceInput('1.999')).toBe('invalid');
    expect(parsePriceInput('1e3')).toBe('invalid');
  });
});

describe('priceToInput', () => {
  it('round-trips with the locale decimal separator', () => {
    expect(priceToInput(4.5, 'fr')).toBe('4,50');
    expect(priceToInput(4.5, 'en')).toBe('4.50');
    expect(priceToInput(10, 'fr')).toBe('10');
    expect(priceToInput(null, 'en')).toBe('');
    expect(parsePriceInput(priceToInput(4.5, 'fr'))).toBe(4.5);
  });
});

describe('isPriceRangeValid / toggleTag', () => {
  it('validates the range', () => {
    expect(isPriceRangeValid({ minPrice: 2, maxPrice: 5 })).toBe(true);
    expect(isPriceRangeValid({ minPrice: 5, maxPrice: 5 })).toBe(true);
    expect(isPriceRangeValid({ minPrice: 6, maxPrice: 5 })).toBe(false);
    expect(isPriceRangeValid({ minPrice: null, maxPrice: 5 })).toBe(true);
  });

  it('toggles dietary tags', () => {
    expect(toggleTag([], 'vegan')).toEqual(['vegan']);
    expect(toggleTag(['vegan', 'organic'], 'vegan')).toEqual(['organic']);
  });
});

describe('countActiveFilters', () => {
  it('is 0 for the defaults and counts each tag', () => {
    expect(countActiveFilters(EMPTY_FILTERS)).toBe(0);
    expect(
      countActiveFilters({
        ...EMPTY_FILTERS,
        minPrice: 1,
        maxPrice: 3,
        brand: ' Fermette ',
        tags: ['vegan', 'organic'],
        onSaleOnly: true,
        radiusKm: 5,
        sort: 'unit_price',
      }),
    ).toBe(7);
  });
});

describe('toOffersQuery', () => {
  const base = { lat: 45.5, lon: -73.56, q: '', section: null, defaultRadiusKm: 10 };

  it('sends only the non-default parameters', () => {
    expect(toOffersQuery(EMPTY_FILTERS, base)).toEqual({
      lat: 45.5,
      lon: -73.56,
      radius_km: 10,
      sort: 'price',
      limit: OFFERS_PAGE_SIZE,
      offset: 0,
    });
  });

  it('maps every filter', () => {
    expect(
      toOffersQuery(
        {
          minPrice: 1,
          maxPrice: 4.5,
          brand: ' Fermette ',
          chain: 'Marché Soleil',
          tags: ['organic'],
          onSaleOnly: true,
          radiusKm: 5,
          sort: 'distance',
        },
        { ...base, q: '  lait ', section: 'dairy', offset: 30 },
      ),
    ).toEqual({
      lat: 45.5,
      lon: -73.56,
      radius_km: 5,
      q: 'lait',
      section: 'dairy',
      brand: 'Fermette',
      chain: 'Marché Soleil',
      tags: ['organic'],
      on_sale: true,
      min_price: 1,
      max_price: 4.5,
      sort: 'distance',
      limit: OFFERS_PAGE_SIZE,
      offset: 30,
    });
  });
});
