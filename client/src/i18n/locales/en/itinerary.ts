import type fr from '../fr/itinerary';

const itinerary: typeof fr = {
  title: 'Itinerary',
  open_in_maps: 'Open in Google Maps',
  open_maps_error: 'Could not open Google Maps.',
  done: 'Done',
  planning: 'Planning the fastest route…',
  map_label: 'Route map: start and {count} stop(s)',
  map_unavailable: 'Map unavailable: check your Internet connection.',
  start: 'Start',
  stop_label: 'Stop {order}',
  leg: '{distance} · {duration}',
  arrival: 'Arrival after {duration}',
  total_distance: 'Distance',
  total_duration: 'Duration',
  stops: 'Stops',
  to_buy: 'To buy here',
  item_line: '{quantity} × {name}',
  travel_mode_label: 'Travel mode',
  estimate_notice:
    'Estimated times: the routing service is unavailable, so distances are straight lines with a detour margin.',
  location_needed: 'Your location is needed to plan the route.',
  empty_title: 'No route to plan',
  empty_message: 'Approve the items of your list to plan your route.',
  back_to_results: 'Back to results',
  demo_store_address: 'Demo store, fictional location',
  travel_mode: {
    driving: 'By car',
    walking: 'On foot',
    cycling: 'By bike',
  },
};

export default itinerary;
