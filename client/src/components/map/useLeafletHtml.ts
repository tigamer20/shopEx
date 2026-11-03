import { useMemo } from 'react';

import { TILE_URL } from '@/config';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';

import { buildLeafletHtml } from './leafletHtml';
import type { ItineraryMapProps } from './types';

export interface LeafletPage {
  html: string;
  /** Spoken description of the map for screen readers. */
  accessibilityLabel: string;
}

/** Builds the themed, translated Leaflet page for an itinerary (shared by web and native). */
export function useLeafletHtml({ start, stops, geometry }: ItineraryMapProps): LeafletPage {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();

  return useMemo(() => {
    const accessibilityLabel = t('itinerary.map_label', { count: stops.length });
    const html = buildLeafletHtml({
      start,
      stops: stops.map((stop) => ({
        order: stop.order,
        lat: stop.store.lat,
        lon: stop.store.lon,
        name: stop.store.name,
      })),
      geometry,
      tileUrl: TILE_URL,
      language,
      colors: {
        primary: theme.colors.primary,
        onPrimary: theme.colors.onPrimary,
        text: theme.colors.text,
        background: theme.colors.surface,
      },
      labels: {
        map: accessibilityLabel,
        start: t('itinerary.start'),
        unavailable: t('itinerary.map_unavailable'),
      },
    });
    return { html, accessibilityLabel };
  }, [start, stops, geometry, language, t, theme]);
}
