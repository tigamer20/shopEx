/**
 * Typed HTTP client for the ShopEx API (ARCHITECTURE §4): JSON in/out, request timeout,
 * bearer-token injection and one function per endpoint.
 *
 * The auth layer (`AuthProvider`) registers the current token with `setApiToken()` and a
 * logout callback with `setUnauthorizedHandler()`; screens never handle tokens themselves.
 */
import { API_BASE_URL } from '@/config';

import type {
  ApiErrorBody,
  GroceryList,
  GroceryListCreate,
  GroceryListSummary,
  GroceryListUpdate,
  HealthResponse,
  ItineraryRequest,
  ItineraryResponse,
  ListsQuery,
  LoginRequest,
  OffersQuery,
  OffersResponse,
  RegisterRequest,
  SearchRequest,
  SearchResponse,
  Section,
  Store,
  StoresQuery,
  TokenResponse,
  User,
  UserUpdate,
  ValidationErrorItem,
} from './types';

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/**
 * - `http`: the server answered with a non-2xx status (`status` is that code).
 * - `network`: no response (offline, DNS, CORS...). `status` is 0.
 * - `timeout`: no response within the timeout. `status` is 0.
 * - `aborted`: the caller cancelled the request through its AbortSignal. `status` is 0.
 */
export type ApiErrorKind = 'http' | 'network' | 'timeout' | 'aborted';

export type ApiErrorDetail = string | ValidationErrorItem[] | null;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: ApiErrorDetail;
  readonly kind: ApiErrorKind;

  constructor(status: number, detail: ApiErrorDetail, kind: ApiErrorKind = 'http') {
    super(ApiError.describe(status, detail, kind));
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.kind = kind;
  }

  private static describe(status: number, detail: ApiErrorDetail, kind: ApiErrorKind): string {
    if (kind !== 'http') {
      return `Request failed (${kind})`;
    }
    const text = typeof detail === 'string' ? detail : detail?.map((item) => item.msg).join('; ');
    return text ? `HTTP ${status}: ${text}` : `HTTP ${status}`;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** True when the caller cancelled the request; screens usually ignore these. */
export function isAbortError(error: unknown): boolean {
  return isApiError(error) && error.kind === 'aborted';
}

// ---------------------------------------------------------------------------
// Auth bridge
// ---------------------------------------------------------------------------

let currentToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

/** Called by the auth layer whenever the session token changes. */
export function setApiToken(token: string | null): void {
  currentToken = token;
}

/** Called once by the auth layer; invoked when an authenticated request gets a 401. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

// ---------------------------------------------------------------------------
// Request core
// ---------------------------------------------------------------------------

export interface RequestOptions {
  /** Cancels the request (e.g. when a screen unmounts). */
  signal?: AbortSignal;
  /** Overrides the default timeout for this call. */
  timeoutMs?: number;
}

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';
type QueryValue = string | number | boolean | string[] | null | undefined;
type QueryParams = Record<string, QueryValue>;

interface RequestConfig extends RequestOptions {
  method: HttpMethod;
  query?: QueryParams;
  body?: unknown;
}

export const DEFAULT_TIMEOUT_MS = 20_000;
/** /search and /itinerary may discover stores or call OSRM server-side: allow more time. */
const SLOW_TIMEOUT_MS = 60_000;

function buildQuery(params: QueryParams | undefined): string {
  if (!params) {
    return '';
  }
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    const serialized = Array.isArray(value) ? value.join(',') : String(value);
    if (serialized) {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(serialized)}`);
    }
  }
  return parts.length > 0 ? `?${parts.join('&')}` : '';
}

/** Validates a numeric path parameter so it can never alter the URL path. */
function pathId(id: number): string {
  if (!Number.isSafeInteger(id) || id < 1) {
    throw new RangeError(`Invalid resource id: ${id}`);
  }
  return String(id);
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }
  const text = await response.text();
  if (!text) {
    return undefined;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function extractDetail(payload: unknown): ApiErrorDetail {
  if (typeof payload === 'string') {
    return payload;
  }
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const { detail } = payload as ApiErrorBody;
    if (typeof detail === 'string' || Array.isArray(detail)) {
      return detail;
    }
  }
  return null;
}

async function request<T>(path: string, config: RequestConfig): Promise<T> {
  const { method, query, body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = config;
  const url = `${API_BASE_URL}${path}${buildQuery(query)}`;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = (): void => controller.abort();
  if (signal?.aborted) {
    controller.abort();
  }
  signal?.addEventListener('abort', forwardAbort);

  // Capture the token used for this call so a late 401 cannot log out a newer session.
  const token = currentToken;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  let payload: unknown;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    payload = await readBody(response);
  } catch {
    if (timedOut) {
      throw new ApiError(0, null, 'timeout');
    }
    if (signal?.aborted) {
      throw new ApiError(0, null, 'aborted');
    }
    throw new ApiError(0, null, 'network');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', forwardAbort);
  }

  if (!response.ok) {
    if (response.status === 401 && token !== null && token === currentToken) {
      unauthorizedHandler?.();
    }
    throw new ApiError(response.status, extractDetail(payload));
  }
  return payload as T;
}

// ---------------------------------------------------------------------------
// Auth & user
// ---------------------------------------------------------------------------

export function registerUser(body: RegisterRequest, options?: RequestOptions): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/register', { method: 'POST', body, ...options });
}

export function loginUser(body: LoginRequest, options?: RequestOptions): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', { method: 'POST', body, ...options });
}

export function fetchMe(options?: RequestOptions): Promise<User> {
  return request<User>('/users/me', { method: 'GET', ...options });
}

export function updateMe(body: UserUpdate, options?: RequestOptions): Promise<User> {
  return request<User>('/users/me', { method: 'PATCH', body, ...options });
}

/** Deletes the account and all its lists (204). */
export function deleteMe(options?: RequestOptions): Promise<void> {
  return request<void>('/users/me', { method: 'DELETE', ...options });
}

// ---------------------------------------------------------------------------
// Lists (history & bookmarks)
// ---------------------------------------------------------------------------

/** History (all lists) or bookmarks only, ordered by `last_used_at` desc. */
export function fetchLists(query: ListsQuery = {}, options?: RequestOptions): Promise<GroceryListSummary[]> {
  return request<GroceryListSummary[]>('/lists', { method: 'GET', query: { ...query }, ...options });
}

export function createList(body: GroceryListCreate, options?: RequestOptions): Promise<GroceryList> {
  return request<GroceryList>('/lists', { method: 'POST', body, ...options });
}

export function fetchList(id: number, options?: RequestOptions): Promise<GroceryList> {
  return request<GroceryList>(`/lists/${pathId(id)}`, { method: 'GET', ...options });
}

export function updateList(id: number, body: GroceryListUpdate, options?: RequestOptions): Promise<GroceryList> {
  return request<GroceryList>(`/lists/${pathId(id)}`, { method: 'PATCH', body, ...options });
}

export function deleteList(id: number, options?: RequestOptions): Promise<void> {
  return request<void>(`/lists/${pathId(id)}`, { method: 'DELETE', ...options });
}

// ---------------------------------------------------------------------------
// Stores & catalog
// ---------------------------------------------------------------------------

/** Stores around a point, sorted by distance (the server discovers the area if needed). */
export function fetchStores(query: StoresQuery, options?: RequestOptions): Promise<Store[]> {
  return request<Store[]>('/stores', {
    method: 'GET',
    query: { ...query },
    timeoutMs: SLOW_TIMEOUT_MS,
    ...options,
  });
}

export function fetchSections(options?: RequestOptions): Promise<Section[]> {
  return request<Section[]>('/catalog/sections', { method: 'GET', ...options });
}

export function fetchOffers(query: OffersQuery, options?: RequestOptions): Promise<OffersResponse> {
  return request<OffersResponse>('/catalog/offers', {
    method: 'GET',
    query: { ...query },
    timeoutMs: SLOW_TIMEOUT_MS,
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Search & itinerary
// ---------------------------------------------------------------------------

/** Cheapest offer + 2 alternatives for every item of a grocery list. */
export function searchPrices(body: SearchRequest, options?: RequestOptions): Promise<SearchResponse> {
  return request<SearchResponse>('/search', {
    method: 'POST',
    body,
    timeoutMs: SLOW_TIMEOUT_MS,
    ...options,
  });
}

/** Fastest visiting order for the chosen stores. */
export function planItinerary(body: ItineraryRequest, options?: RequestOptions): Promise<ItineraryResponse> {
  return request<ItineraryResponse>('/itinerary', {
    method: 'POST',
    body,
    timeoutMs: SLOW_TIMEOUT_MS,
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function fetchHealth(options?: RequestOptions): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { method: 'GET', ...options });
}
