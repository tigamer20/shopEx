/**
 * TypeScript mirror of the HTTP contract (ARCHITECTURE §4).
 * Field names are snake_case, identical to the Pydantic models in `backend/app/schemas.py`.
 * Timestamps are ISO-8601 strings (timezone-aware UTC).
 */

// ---------------------------------------------------------------------------
// Shared enums
// ---------------------------------------------------------------------------

export type Language = 'fr' | 'en';
export type TravelMode = 'driving' | 'walking' | 'cycling';
export type SortBy = 'price' | 'unit_price' | 'distance';
export type DietaryTag =
  | 'organic'
  | 'gluten_free'
  | 'vegan'
  | 'vegetarian'
  | 'lactose_free'
  | 'local'
  | 'store_brand';

export type StoreSource = 'osm' | 'demo';
export type PriceTier = 'discount' | 'standard' | 'premium';
export type SizeUnit = 'g' | 'kg' | 'ml' | 'L' | 'unit';
export type UnitPriceUnit = 'kg' | 'L' | 'unit';
export type RoutingSource = 'osrm' | 'estimate';

/** ISO-8601 date-time string. */
export type IsoDateTime = string;

export const LANGUAGES: readonly Language[] = ['fr', 'en'];
export const TRAVEL_MODES: readonly TravelMode[] = ['driving', 'walking', 'cycling'];
export const SORT_OPTIONS: readonly SortBy[] = ['price', 'unit_price', 'distance'];
export const DIETARY_TAGS: readonly DietaryTag[] = [
  'organic',
  'gluten_free',
  'vegan',
  'vegetarian',
  'lactose_free',
  'local',
  'store_brand',
];

// ---------------------------------------------------------------------------
// Auth & user
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  email: string;
  display_name: string;
  language: Language;
  search_radius_km: number;
  travel_mode: TravelMode;
  tutorial_completed: boolean;
  created_at: IsoDateTime;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

/** `POST /auth/register` — password 8..128 chars, display_name 1..60 chars. */
export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
  language?: Language;
}

/** `POST /auth/login` */
export interface LoginRequest {
  email: string;
  password: string;
}

/** `PATCH /users/me` — search_radius_km 1..50. */
export interface UserUpdate {
  display_name?: string;
  language?: Language;
  search_radius_km?: number;
  travel_mode?: TravelMode;
  tutorial_completed?: boolean;
}

// ---------------------------------------------------------------------------
// Lists (history & bookmarks)
// ---------------------------------------------------------------------------

/** name 1..100 chars, brand ≤ 60 chars (null = any brand), quantity 1..99. */
export interface GroceryItemInput {
  name: string;
  brand: string | null;
  quantity: number;
}

export interface GroceryList {
  id: number;
  name: string;
  items: GroceryItemInput[];
  bookmarked: boolean;
  created_at: IsoDateTime;
  last_used_at: IsoDateTime;
}

export interface GroceryListSummary {
  id: number;
  name: string;
  items_count: number;
  bookmarked: boolean;
  created_at: IsoDateTime;
  last_used_at: IsoDateTime;
}

/** `POST /lists` — name 1..80 chars, 1..100 items. */
export interface GroceryListCreate {
  name: string;
  items: GroceryItemInput[];
  bookmarked?: boolean;
}

/** `PATCH /lists/{id}` */
export interface GroceryListUpdate {
  name?: string;
  items?: GroceryItemInput[];
  bookmarked?: boolean;
}

/** `GET /lists?bookmarked=` — omit `bookmarked` to get every list. */
export interface ListsQuery {
  bookmarked?: boolean;
}

// ---------------------------------------------------------------------------
// Stores & catalog
// ---------------------------------------------------------------------------

export interface Store {
  id: number;
  name: string;
  chain: string | null;
  address: string | null;
  lat: number;
  lon: number;
  distance_km: number | null;
  source: StoreSource;
  price_tier: PriceTier;
}

export interface Section {
  id: string;
  name_fr: string;
  name_en: string;
}

export interface Product {
  id: number;
  slug: string;
  name_fr: string;
  name_en: string;
  brand: string;
  section_id: string;
  size_value: number;
  size_unit: SizeUnit;
  tags: DietaryTag[];
}

export interface Offer {
  price_id: number;
  product: Product;
  store: Store;
  price: number;
  regular_price: number;
  on_sale: boolean;
  unit_price: number;
  unit_price_unit: UnitPriceUnit;
  updated_at: IsoDateTime;
  source: string;
}

/** `GET /stores` — radius defaults to the user's, capped by the server's MAX_RADIUS_KM. */
export interface StoresQuery {
  lat: number;
  lon: number;
  radius_km?: number;
}

/** `GET /catalog/offers` — `tags` is sent as a comma list; limit 1..100 (default 30). */
export interface OffersQuery {
  lat: number;
  lon: number;
  radius_km?: number;
  q?: string;
  section?: string;
  brand?: string;
  chain?: string;
  tags?: DietaryTag[];
  on_sale?: boolean;
  min_price?: number;
  max_price?: number;
  store_id?: number;
  sort?: SortBy;
  limit?: number;
  offset?: number;
}

export interface OffersResponse {
  items: Offer[];
  total: number;
  prices_are_demo: boolean;
}

// ---------------------------------------------------------------------------
// Search (the core flow)
// ---------------------------------------------------------------------------

export interface SearchFilters {
  tags?: DietaryTag[];
  on_sale_only?: boolean;
  max_price?: number;
  exclude_chains?: string[];
  sort_by?: 'price' | 'unit_price';
}

/** `POST /search` — 1..100 items; `save_to_history` defaults to true server-side. */
export interface SearchRequest {
  lat: number;
  lon: number;
  radius_km?: number;
  items: GroceryItemInput[];
  filters?: SearchFilters;
  save_to_history?: boolean;
  list_name?: string;
  list_id?: number;
}

/** i18n keys the server may return in `ItemResult.message_key`. */
export type SearchMessageKey = 'search.no_match' | 'search.brand_not_found';

export interface ItemResult {
  query: GroceryItemInput;
  matched: boolean;
  /** null when no brand was requested; false when the requested brand was not found. */
  brand_matched: boolean | null;
  best: Offer | null;
  /** 0..2 alternative offers. */
  alternatives: Offer[];
  line_total: number | null;
  /** i18n key (see `SearchMessageKey`); typed as string because the server owns the list. */
  message_key: string | null;
}

export interface SearchResponse {
  list_id: number | null;
  prices_are_demo: boolean;
  currency: 'CAD';
  results: ItemResult[];
  stores: Store[];
  best_total: number;
}

// ---------------------------------------------------------------------------
// Itinerary
// ---------------------------------------------------------------------------

export interface LatLon {
  lat: number;
  lon: number;
}

/** `POST /itinerary` — 1..15 unique store ids. */
export interface ItineraryRequest {
  start: LatLon;
  store_ids: number[];
  travel_mode?: TravelMode;
  return_to_start?: boolean;
}

export interface ItineraryStop {
  /** 1-based visiting order. */
  order: number;
  store: Store;
  leg_distance_km: number;
  leg_duration_min: number;
  arrival_min: number;
}

export interface ItineraryResponse {
  stops: ItineraryStop[];
  total_distance_km: number;
  total_duration_min: number;
  /** Route line as [lat, lon] pairs, or null when only an estimate is available. */
  geometry: [number, number][] | null;
  routing_source: RoutingSource;
  maps_url: string;
}

// ---------------------------------------------------------------------------
// Admin & health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: 'ok';
  version: string;
}

/** `POST /admin/refresh` response (server-to-server only; the app never calls it). */
export interface RefreshResult {
  areas_refreshed: number;
  stores_refreshed: number;
  prices_updated: number;
  started_at: IsoDateTime;
  finished_at: IsoDateTime;
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/** One entry of FastAPI's 422 validation `detail` array. */
export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** FastAPI error body: `{"detail": ...}`. */
export interface ApiErrorBody {
  detail: string | ValidationErrorItem[];
}
