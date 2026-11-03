import { DEFAULT_TILE_URL } from '@/config';

import { buildLeafletHtml, LEAFLET_ASSETS, safeTileUrl, type LeafletHtmlOptions } from '../leafletHtml';

function options(overrides: Partial<LeafletHtmlOptions> = {}): LeafletHtmlOptions {
  return {
    start: { lat: 45.5, lon: -73.56 },
    stops: [
      { order: 1, lat: 45.51, lon: -73.57, name: 'Marché Soleil' },
      { order: 2, lat: 45.52, lon: -73.58, name: 'Épicerie du Coin' },
    ],
    geometry: null,
    tileUrl: DEFAULT_TILE_URL,
    colors: { primary: '#F2542D', onPrimary: '#FFFFFF', text: '#191919', background: '#F5F5F5' },
    language: 'fr',
    labels: { map: 'Carte du trajet', start: 'Départ', unavailable: 'Carte indisponible' },
    ...overrides,
  };
}

/** Extracts the JSON payload handed to the inline script. */
function payload(html: string): Record<string, unknown> {
  const match = /var data = (.*);\n/.exec(html);
  if (!match?.[1]) {
    throw new Error('payload not found');
  }
  return JSON.parse(match[1]) as Record<string, unknown>;
}

describe('buildLeafletHtml', () => {
  it('loads Leaflet 1.9.4 from unpkg with the vetted SRI hashes and crossorigin', () => {
    const html = buildLeafletHtml(options());
    expect(html).toContain(
      '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH" crossorigin=""></script>',
    );
    expect(html).toContain(
      '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H" crossorigin="">',
    );
    expect(LEAFLET_ASSETS.script.url).toContain('@1.9.4');
  });

  it('only loads scripts and styles from unpkg (no default marker images)', () => {
    const html = buildLeafletHtml(options());
    const sources = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((match) => match[1]);
    expect(sources).toEqual([LEAFLET_ASSETS.stylesheet.url, LEAFLET_ASSETS.script.url]);
    expect(html).toContain('L.divIcon');
    expect(html).not.toContain('marker-icon');
  });

  it('shows the OpenStreetMap attribution and the configured tiles', () => {
    const data = payload(buildLeafletHtml(options()));
    expect(data.attribution).toContain('OpenStreetMap</a> contributors');
    expect(data.tileUrl).toBe(DEFAULT_TILE_URL);
  });

  it('numbers the stops and HTML-escapes store names', () => {
    const html = buildLeafletHtml(
      options({ stops: [{ order: 1, lat: 45.51, lon: -73.57, name: '<img src=x onerror=alert(1)> & Co' }] }),
    );
    expect(html).not.toContain('<img src=x');
    const data = payload(html) as { stops: { order: number; label: string }[] };
    expect(data.stops).toEqual([
      { at: [45.51, -73.57], order: 1, label: '1. &lt;img src=x onerror=alert(1)&gt; &amp; Co' },
    ]);
  });

  it('cannot be broken out of by a hostile name', () => {
    const html = buildLeafletHtml(
      options({ stops: [{ order: 1, lat: 45.51, lon: -73.57, name: '</script><script>alert(1)</script>' }] }),
    );
    expect(html.match(/<\/script>/g)).toHaveLength(2);
  });

  it('draws the server route when present, else straight segments from the start', () => {
    const withRoute = payload(
      buildLeafletHtml(
        options({
          geometry: [
            [45.5, -73.56],
            [45.505, -73.565],
            [45.52, -73.58],
          ],
        }),
      ),
    ) as { route: { points: number[][]; estimated: boolean } };
    expect(withRoute.route.estimated).toBe(false);
    expect(withRoute.route.points).toHaveLength(3);

    const straight = payload(buildLeafletHtml(options())) as { route: { points: number[][]; estimated: boolean } };
    expect(straight.route).toEqual({
      points: [
        [45.5, -73.56],
        [45.51, -73.57],
        [45.52, -73.58],
      ],
      estimated: true,
    });
  });

  it('drops invalid coordinates and sanitises colours and language', () => {
    const html = buildLeafletHtml(
      options({
        stops: [{ order: 1, lat: 999, lon: 0, name: 'Nowhere' }],
        colors: { primary: 'red;}</style>', onPrimary: '#FFF', text: '#000', background: '#FFF' },
        language: '"><x',
      }),
    );
    const data = payload(html) as { stops: unknown[]; routeColor: string };
    expect(data.stops).toEqual([]);
    expect(data.routeColor).toBe('#F2542D');
    expect(html).toContain('<html lang="fr">');
    expect(html).not.toContain('red;}');
  });
});

describe('safeTileUrl', () => {
  it('keeps http(s) templates with placeholders', () => {
    expect(safeTileUrl('https://tiles.example.org/{z}/{x}/{y}.png')).toBe('https://tiles.example.org/{z}/{x}/{y}.png');
  });

  it('falls back to OpenStreetMap for anything else', () => {
    expect(safeTileUrl('javascript:alert(1)//{z}{x}{y}')).toBe(DEFAULT_TILE_URL);
    expect(safeTileUrl('https://tiles.example.org/static.png')).toBe(DEFAULT_TILE_URL);
    expect(safeTileUrl('https://x/{z}/{x}/{y}"onload="')).toBe(DEFAULT_TILE_URL);
  });
});
