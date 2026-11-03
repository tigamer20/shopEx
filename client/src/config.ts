/**
 * Client configuration (ARCHITECTURE §5 "Configuration").
 * EXPO_PUBLIC_* variables are inlined at build time; they must never hold secrets.
 */

export const DEFAULT_API_URL = 'http://localhost:8000';
export const DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

const SCHEME_PATTERN = /^[a-z][a-z\d+.-]*:\/\//i;

/**
 * Normalises the API origin: blank → default, missing scheme → `https://`, no trailing slash.
 * The scheme rule lets a bare host name (`shopex-api.onrender.com`) be configured.
 */
export function normalizeApiUrl(raw: string | null | undefined): string {
  const trimmed = (raw ?? '').trim();
  if (!trimmed) {
    return DEFAULT_API_URL;
  }
  const withScheme = SCHEME_PATTERN.test(trimmed) ? trimmed : `https://${trimmed}`;
  return withScheme.replace(/\/+$/, '');
}

/** Tile URL template for Leaflet; blank → OpenStreetMap's standard tiles. */
export function normalizeTileUrl(raw: string | null | undefined): string {
  const trimmed = (raw ?? '').trim();
  return trimmed || DEFAULT_TILE_URL;
}

/** API origin, e.g. `https://shopex-api.onrender.com`. */
export const API_URL = normalizeApiUrl(process.env.EXPO_PUBLIC_API_URL);

/** Base URL every endpoint path of §4 is appended to. */
export const API_BASE_URL = `${API_URL}/api/v1`;

export const TILE_URL = normalizeTileUrl(process.env.EXPO_PUBLIC_TILE_URL);
