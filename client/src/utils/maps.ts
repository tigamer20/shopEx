/**
 * Map helpers shared by the itinerary screen and the Leaflet map page:
 * Google Maps directions links, coordinate checks and HTML/script-safe serialisation.
 */
import type { LatLon, TravelMode } from '@/api/types';

/** Only links of this shape are handed to `Linking.openURL` (the server builds them, §4). */
const GOOGLE_MAPS_URL_PATTERN = /^https:\/\/(www\.)?google\.com\/maps\/[^\s]*$/;

/** True for an `https://www.google.com/maps/...` link without whitespace. */
export function isGoogleMapsUrl(url: string | null | undefined): url is string {
  return typeof url === 'string' && GOOGLE_MAPS_URL_PATTERN.test(url);
}

/** Google Maps names the bike profile `bicycling`. */
const GOOGLE_TRAVEL_MODES: Record<TravelMode, string> = {
  driving: 'driving',
  walking: 'walking',
  cycling: 'bicycling',
};

/** True when both values are finite and within WGS-84 bounds. */
export function isValidCoordinate(point: LatLon | null | undefined): point is LatLon {
  return (
    !!point &&
    Number.isFinite(point.lat) &&
    Number.isFinite(point.lon) &&
    Math.abs(point.lat) <= 90 &&
    Math.abs(point.lon) <= 180
  );
}

function formatPoint(point: LatLon): string {
  // 6 decimals ≈ 10 cm: plenty for directions, and keeps the URL short.
  return `${point.lat.toFixed(6)},${point.lon.toFixed(6)}`;
}

/**
 * Client-side fallback for `ItineraryResponse.maps_url`: directions from `start` through every
 * stop in order (`https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=a|b`).
 */
export function buildGoogleMapsUrl(start: LatLon, stops: readonly LatLon[], mode: TravelMode): string {
  const valid = stops.filter(isValidCoordinate);
  const destination = valid.at(-1) ?? start;
  const params = [
    'api=1',
    `origin=${encodeURIComponent(formatPoint(start))}`,
    `destination=${encodeURIComponent(formatPoint(destination))}`,
  ];
  const waypoints = valid.slice(0, -1);
  if (waypoints.length > 0) {
    params.push(`waypoints=${encodeURIComponent(waypoints.map(formatPoint).join('|'))}`);
  }
  params.push(`travelmode=${GOOGLE_TRAVEL_MODES[mode]}`);
  return `https://www.google.com/maps/dir/?${params.join('&')}`;
}

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Escapes text for use inside HTML element content or a quoted attribute. */
export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char] ?? char);
}

/**
 * JSON for embedding inside an inline `<script>`: `<`, `>`, `&` and the JS line separators are
 * escaped so a value can never close the script element or break the statement.
 */
export function toScriptJson(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

/** `POST /itinerary` accepts 1..15 unique stores (ARCHITECTURE §4). */
export const MAX_ITINERARY_STORES = 15;
