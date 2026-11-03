import type fr from '../fr/browse';

const browse: typeof fr = {
  title: 'Browse',
  search_placeholder: 'Search for a product',
  search_label: 'Search the catalog',
  clear_search: 'Clear search',
  filters: 'Filters',
  filters_active: 'Filters ({count})',
  all_sections: 'All',
  sections_label: 'Sections',
  open_filters: 'Open filters',
  results_count: '{count} offer(s)',
  empty_title: 'No offers found',
  empty_message: 'Try another search or remove some filters.',
  location_needed: 'Your location is needed to show offers from the grocery stores near you.',
  filter_sheet: {
    price_range: 'Price range',
    min_price: 'Minimum price ($)',
    max_price: 'Maximum price ($)',
    price_placeholder: 'None',
    invalid_price: 'Enter a valid price (e.g. 4.99).',
    invalid_range: 'The minimum price must be lower than or equal to the maximum price.',
    brand: 'Brand',
    brand_placeholder: 'Any brand',
    chain: 'Chain',
    chain_placeholder: 'Any chain',
    tags: 'Dietary preferences',
    on_sale_only: 'On sale only',
    distance: 'Maximum distance',
    distance_value: '{km} km',
    distance_default: 'My radius ({km} km)',
    sort: 'Sort by',
  },
  sort: {
    price: 'Price',
    unit_price: 'Unit price',
    distance: 'Distance',
  },
};

export default browse;
