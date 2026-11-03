import { buildGoogleMapsUrl, escapeHtml, isGoogleMapsUrl, isValidCoordinate, toScriptJson } from '../maps';

describe('isGoogleMapsUrl', () => {
  it('accepts Google Maps directions links', () => {
    expect(isGoogleMapsUrl('https://www.google.com/maps/dir/?api=1&origin=1,2&destination=3,4')).toBe(true);
    expect(isGoogleMapsUrl('https://google.com/maps/dir/?api=1')).toBe(true);
  });

  it('rejects other schemes, hosts and malformed values', () => {
    expect(isGoogleMapsUrl('http://www.google.com/maps/dir/')).toBe(false);
    expect(isGoogleMapsUrl('https://www.google.com.evil.example/maps/dir/')).toBe(false);
    expect(isGoogleMapsUrl('https://evil.example/https://www.google.com/maps/')).toBe(false);
    expect(isGoogleMapsUrl('javascript:alert(1)')).toBe(false);
    expect(isGoogleMapsUrl('https://www.google.com/maps/dir/ x')).toBe(false);
    expect(isGoogleMapsUrl(null)).toBe(false);
  });
});

describe('buildGoogleMapsUrl', () => {
  const start = { lat: 45.5, lon: -73.56 };

  it('routes through every stop in order', () => {
    const url = buildGoogleMapsUrl(
      start,
      [
        { lat: 45.51, lon: -73.57 },
        { lat: 45.52, lon: -73.58 },
        { lat: 45.53, lon: -73.59 },
      ],
      'cycling',
    );
    expect(url).toBe(
      'https://www.google.com/maps/dir/?api=1' +
        '&origin=45.500000%2C-73.560000' +
        '&destination=45.530000%2C-73.590000' +
        '&waypoints=45.510000%2C-73.570000%7C45.520000%2C-73.580000' +
        '&travelmode=bicycling',
    );
    expect(isGoogleMapsUrl(url)).toBe(true);
  });

  it('omits waypoints for a single stop and skips invalid points', () => {
    const url = buildGoogleMapsUrl(start, [{ lat: Number.NaN, lon: 0 }, { lat: 45.51, lon: -73.57 }], 'walking');
    expect(url).not.toContain('waypoints');
    expect(url).toContain('destination=45.510000%2C-73.570000');
    expect(url).toContain('travelmode=walking');
  });
});

describe('isValidCoordinate', () => {
  it('checks finiteness and WGS-84 bounds', () => {
    expect(isValidCoordinate({ lat: 45, lon: -73 })).toBe(true);
    expect(isValidCoordinate({ lat: 91, lon: 0 })).toBe(false);
    expect(isValidCoordinate({ lat: 0, lon: 181 })).toBe(false);
    expect(isValidCoordinate({ lat: Number.POSITIVE_INFINITY, lon: 0 })).toBe(false);
    expect(isValidCoordinate(null)).toBe(false);
  });
});

describe('escapeHtml', () => {
  it('escapes the five HTML-significant characters', () => {
    expect(escapeHtml(`<b class="x">Tom & Jerry's</b>`)).toBe(
      '&lt;b class=&quot;x&quot;&gt;Tom &amp; Jerry&#39;s&lt;/b&gt;',
    );
  });
});

describe('toScriptJson', () => {
  it('cannot close a script element and stays valid JSON', () => {
    const value = { name: '</script><script>alert(1)</script>', sep: '\u2028\u2029', amp: 'a&b' };
    const json = toScriptJson(value);
    expect(json).not.toMatch(/[<>&\u2028\u2029]/);
    expect(JSON.parse(json)).toEqual(value);
  });
});
