import type fr from '../fr/results';

const results: typeof fr = {
  title: 'Best prices',
  see_more: 'See more options',
  see_more_for: 'See more options for {name}',
  plan_route: 'Plan my route',
  approve_all: 'Approve all',
  approve: 'Approve',
  approved: 'Approved',
  approve_item: 'Approve {name}',
  choose_this: 'Choose this one',
  current_choice: 'Current choice',
  cheapest: 'Cheapest',
  no_alternatives: 'No other option nearby.',
  line_total: '{quantity} × {price} = {total}',
  requested: 'Your item: {name}',
  requested_brand: 'Requested brand: {brand}',
  not_found: 'Not found',
  quantity_short: 'Qty: {count}',
  total: 'Total of your choices',
  stores_count: '{count} store(s)',
  approved_count: '{approved} of {total} approved',
  approve_hint: 'Approve every item to plan your route.',
  no_matches: 'None of your items was found nearby. Edit the list or increase the search radius in your profile.',
  too_many_stores:
    'Your choices span {count} stores, but a route accepts at most {max}. Pick other options to group your shopping.',
  empty_title: 'No search in progress',
  empty_message: 'Create a grocery list to compare prices.',
  new_list: 'Create a list',
};

export default results;
