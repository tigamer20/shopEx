import { DEFAULT_API_URL, DEFAULT_TILE_URL, normalizeApiUrl, normalizeTileUrl } from '../config';

describe('normalizeApiUrl', () => {
  it('falls back to the local API when unset or blank', () => {
    expect(normalizeApiUrl(undefined)).toBe(DEFAULT_API_URL);
    expect(normalizeApiUrl('   ')).toBe(DEFAULT_API_URL);
  });

  it('prepends https:// to a bare host', () => {
    expect(normalizeApiUrl('shopex-api.onrender.com')).toBe('https://shopex-api.onrender.com');
  });

  it('keeps an explicit scheme and strips trailing slashes', () => {
    expect(normalizeApiUrl('http://localhost:8000/')).toBe('http://localhost:8000');
    expect(normalizeApiUrl(' https://api.example.test// ')).toBe('https://api.example.test');
  });
});

describe('normalizeTileUrl', () => {
  it('defaults to OpenStreetMap tiles', () => {
    expect(normalizeTileUrl('')).toBe(DEFAULT_TILE_URL);
    expect(normalizeTileUrl('https://tiles.example.test/{z}/{x}/{y}.png')).toBe(
      'https://tiles.example.test/{z}/{x}/{y}.png',
    );
  });
});
