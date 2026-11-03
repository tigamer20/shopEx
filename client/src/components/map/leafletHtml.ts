/**
 * Self-contained HTML page rendering the itinerary with Leaflet + OpenStreetMap tiles.
 * Used by `ItineraryMap.web.tsx` (`<iframe srcdoc>`) and `ItineraryMap.native.tsx` (WebView).
 *
 * Security: Leaflet is loaded from unpkg with Subresource Integrity (hashes from the vetted
 * dependency list), every value reaches the page through script-safe JSON, store names are
 * HTML-escaped before Leaflet renders them, and markers are `divIcon`s so no unhashed marker
 * image is ever fetched. The page never receives the auth token.
 */
import { DEFAULT_TILE_URL } from '@/config';
import { escapeHtml, isValidCoordinate, toScriptJson } from '@/utils/maps';

import type { LatLon } from '@/api/types';

export const LEAFLET_VERSION = '1.9.4';

/** Leaflet 1.9.4 assets on unpkg with their SRI hashes (verified against the published files). */
export const LEAFLET_ASSETS = {
  script: {
    url: `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`,
    integrity: 'sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH',
  },
  stylesheet: {
    url: `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`,
    integrity: 'sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H',
  },
} as const;

/** OSM attribution (ODbL) shown in the map's corner; links open outside the map. */
export const OSM_ATTRIBUTION_HTML =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

export interface MapStop extends LatLon {
  /** 1-based visiting order, drawn inside the marker. */
  order: number;
  /** Plain-text store name (escaped by the builder). */
  name: string;
}

export interface MapColors {
  primary: string;
  onPrimary: string;
  text: string;
  background: string;
}

export interface LeafletHtmlOptions {
  start: LatLon | null;
  stops: readonly MapStop[];
  /** Route line as `[lat, lon]` pairs; null/short → straight segments between the stops. */
  geometry: readonly (readonly [number, number])[] | null;
  /** Tile URL template (`{z}/{x}/{y}`), e.g. `TILE_URL` from the config. */
  tileUrl: string;
  colors: MapColors;
  language: string;
  /** Translated, plain-text labels. */
  labels: {
    map: string;
    start: string;
    unavailable: string;
  };
}

const HEX_COLOR = /^#[0-9a-f]{3,8}$/i;
const TILE_TEMPLATE = /^https?:\/\/[^\s"'<>\\]+$/;

function safeColor(value: string, fallback: string): string {
  return HEX_COLOR.test(value) ? value : fallback;
}

/** Accepts an http(s) template with `{z}`, `{x}` and `{y}`; anything else → OSM's default. */
export function safeTileUrl(template: string): string {
  const trimmed = template.trim();
  const hasPlaceholders = ['{z}', '{x}', '{y}'].every((part) => trimmed.includes(part));
  return TILE_TEMPLATE.test(trimmed) && hasPlaceholders ? trimmed : DEFAULT_TILE_URL;
}

function toPair(point: LatLon): [number, number] {
  return [point.lat, point.lon];
}

/** Builds the full map document. Pure: same input → same HTML. */
export function buildLeafletHtml(options: LeafletHtmlOptions): string {
  const { colors, labels } = options;
  const stops = options.stops
    .filter((stop) => isValidCoordinate(stop) && Number.isSafeInteger(stop.order))
    .map((stop) => ({
      at: toPair(stop),
      order: stop.order,
      label: escapeHtml(`${stop.order}. ${stop.name}`),
    }));
  const start = isValidCoordinate(options.start) ? toPair(options.start) : null;
  const geometry = (options.geometry ?? []).filter(
    ([lat, lon]) => isValidCoordinate({ lat, lon }),
  );
  const route =
    geometry.length >= 2
      ? { points: geometry, estimated: false }
      : { points: [...(start ? [start] : []), ...stops.map((stop) => stop.at)], estimated: true };

  const primary = safeColor(colors.primary, '#F2542D');
  const data = {
    tileUrl: safeTileUrl(options.tileUrl),
    attribution: OSM_ATTRIBUTION_HTML,
    start,
    startLabel: escapeHtml(labels.start),
    stops,
    route,
    routeColor: primary,
    unavailable: labels.unavailable,
  };

  const onPrimary = safeColor(colors.onPrimary, '#FFFFFF');
  const text = safeColor(colors.text, '#191919');
  const background = safeColor(colors.background, '#FFFFFF');
  const language = /^[a-z]{2}$/.test(options.language) ? options.language : 'fr';

  return `<!DOCTYPE html>
<html lang="${language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="${LEAFLET_ASSETS.stylesheet.url}" integrity="${LEAFLET_ASSETS.stylesheet.integrity}" crossorigin="">
<style>
html, body, #map { height: 100%; margin: 0; padding: 0; background: ${background}; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.sx-pin { display: flex; align-items: center; justify-content: center; box-sizing: border-box;
  width: 30px; height: 30px; border-radius: 50%; border: 2px solid #FFFFFF;
  background: ${primary}; color: ${onPrimary}; font-weight: 800; font-size: 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35); }
.sx-start { width: 22px; height: 22px; background: ${text}; }
.sx-start::after { content: ""; width: 8px; height: 8px; border-radius: 50%; background: #FFFFFF; }
.sx-message { display: flex; height: 100%; align-items: center; justify-content: center;
  padding: 16px; box-sizing: border-box; text-align: center; color: ${text}; }
</style>
</head>
<body>
<div id="map" role="img" aria-label="${escapeHtml(labels.map)}"></div>
<script src="${LEAFLET_ASSETS.script.url}" integrity="${LEAFLET_ASSETS.script.integrity}" crossorigin=""></script>
<script>
(function () {
  var data = ${toScriptJson(data)};
  var container = document.getElementById('map');
  if (!window.L) {
    container.className = 'sx-message';
    container.textContent = data.unavailable;
    return;
  }
  var map = L.map(container, { scrollWheelZoom: false, zoomSnap: 0.5 });
  L.tileLayer(data.tileUrl, { maxZoom: 19, attribution: data.attribution }).addTo(map);

  var bounds = [];
  if (data.route.points.length >= 2) {
    L.polyline(data.route.points, {
      color: data.routeColor,
      weight: 5,
      opacity: 0.85,
      dashArray: data.route.estimated ? '8 8' : null
    }).addTo(map);
    bounds = bounds.concat(data.route.points);
  }
  if (data.start) {
    L.marker(data.start, {
      icon: L.divIcon({ className: '', html: '<div class="sx-pin sx-start"></div>', iconSize: [22, 22], iconAnchor: [11, 11] }),
      keyboard: false
    }).bindTooltip(data.startLabel).addTo(map);
    bounds.push(data.start);
  }
  data.stops.forEach(function (stop) {
    L.marker(stop.at, {
      icon: L.divIcon({ className: '', html: '<div class="sx-pin">' + Number(stop.order) + '</div>', iconSize: [30, 30], iconAnchor: [15, 15] }),
      keyboard: false
    }).bindTooltip(stop.label).addTo(map);
    bounds.push(stop.at);
  });

  if (bounds.length >= 2) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [32, 32], maxZoom: 16 });
  } else if (bounds.length === 1) {
    map.setView(bounds[0], 15);
  } else {
    map.setView([45.5019, -73.5674], 11);
  }
})();
</script>
</body>
</html>`;
}
