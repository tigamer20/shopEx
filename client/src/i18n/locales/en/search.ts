import type fr from '../fr/search';

const search: typeof fr = {
  no_match: 'No matching product found near you.',
  brand_not_found: 'Brand not found: here are the best offers from other brands.',
  offer: {
    on_sale: 'Sale',
    regular_price: 'Regular price {price}',
    unit_count: '{count} unit(s)',
    store_at_distance: '{store} · {distance}',
    brand_size: '{brand} · {size}',
    accessibility: '{product}, {brand}, {size}. {price} at {store}, {distance} away.',
  },
  tags: {
    organic: 'Organic',
    gluten_free: 'Gluten-free',
    vegan: 'Vegan',
    vegetarian: 'Vegetarian',
    lactose_free: 'Lactose-free',
    local: 'Local',
    store_brand: 'Store brand',
  },
};

export default search;
