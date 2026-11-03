import type { ComponentType } from 'react';

import type { ItineraryStop, LatLon } from '@/api/types';

export interface ItineraryMapProps {
  /** The user's position (route origin). */
  start: LatLon;
  stops: readonly ItineraryStop[];
  /** Route line from the server (`[lat, lon]` pairs), or null for straight segments. */
  geometry: readonly (readonly [number, number])[] | null;
  /** Map height in points (default 280). */
  height?: number;
}

/** Implemented per platform: `ItineraryMap.web.tsx` and `ItineraryMap.native.tsx`. */
export type ItineraryMapComponent = ComponentType<ItineraryMapProps>;

export const DEFAULT_MAP_HEIGHT = 280;
