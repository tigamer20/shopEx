/**
 * Foreground location (iOS, Android and web through expo-location).
 * The last fix is cached for the session so screens show a position immediately.
 */
import * as Location from 'expo-location';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { LatLon } from '@/api/types';

/**
 * - `idle`: nothing requested yet (`auto: false`).
 * - `locating`: asking for permission or waiting for a fix.
 * - `granted`: `coords` holds a position.
 * - `denied`: the user refused the permission (`canAskAgain` says if a new prompt is possible).
 * - `unavailable`: location services are off or no fix could be obtained.
 * - `error`: unexpected failure.
 * UI copy for each status lives under `common.location.*`.
 */
export type LocationStatus = 'idle' | 'locating' | 'granted' | 'denied' | 'unavailable' | 'error';

export interface Coordinates extends LatLon {
  /** Accuracy radius in metres, when the platform reports it. */
  accuracy_m: number | null;
}

export interface UseLocationResult {
  status: LocationStatus;
  coords: Coordinates | null;
  /** False when the OS will not show the permission prompt again (open settings instead). */
  canAskAgain: boolean;
  /** Requests permission if needed and fetches a fresh position. */
  refresh: () => Promise<Coordinates | null>;
}

const POSITION_TIMEOUT_MS = 15_000;

let lastKnown: Coordinates | null = null;

function toCoordinates(position: Location.LocationObject): Coordinates {
  return {
    lat: position.coords.latitude,
    lon: position.coords.longitude,
    accuracy_m: position.coords.accuracy ?? null,
  };
}

/** Resolves with null instead of hanging forever on devices that never answer. */
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | null> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => resolve(null), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error: unknown) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

async function readPosition(): Promise<Location.LocationObject | null> {
  try {
    const current = await withTimeout(
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }),
      POSITION_TIMEOUT_MS,
    );
    if (current) {
      return current;
    }
  } catch {
    // Fall back to the last position the OS knows about.
  }
  try {
    return await Location.getLastKnownPositionAsync();
  } catch {
    return null;
  }
}

interface LocateResult {
  status: Exclude<LocationStatus, 'idle' | 'locating'>;
  coords: Coordinates | null;
  canAskAgain: boolean;
}

/** Asks for the foreground permission, then reads a position. Never throws. */
async function locate(): Promise<LocateResult> {
  try {
    const permission = await Location.requestForegroundPermissionsAsync();
    const { canAskAgain } = permission;
    if (permission.status !== Location.PermissionStatus.GRANTED) {
      return { status: 'denied', coords: null, canAskAgain };
    }
    const position = await readPosition();
    if (!position) {
      return { status: 'unavailable', coords: null, canAskAgain };
    }
    lastKnown = toCoordinates(position);
    return { status: 'granted', coords: lastKnown, canAskAgain };
  } catch {
    return { status: 'error', coords: null, canAskAgain: true };
  }
}

export function useLocation({ auto = true }: { auto?: boolean } = {}): UseLocationResult {
  const [status, setStatus] = useState<LocationStatus>(lastKnown ? 'granted' : auto ? 'locating' : 'idle');
  const [coords, setCoords] = useState<Coordinates | null>(lastKnown);
  const [canAskAgain, setCanAskAgain] = useState(true);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /** Stores a result unless the component unmounted meanwhile; a failed fix keeps old coords. */
  const apply = useCallback((result: LocateResult): Coordinates | null => {
    if (mounted.current) {
      setStatus(result.status);
      setCanAskAgain(result.canAskAgain);
      if (result.coords) {
        setCoords(result.coords);
      }
    }
    return result.coords;
  }, []);

  const refresh = useCallback(async (): Promise<Coordinates | null> => {
    setStatus('locating');
    return apply(await locate());
  }, [apply]);

  // Initial state is already `locating` (or `granted` from the cache) when auto is on.
  useEffect(() => {
    if (auto) {
      void locate().then(apply);
    }
  }, [auto, apply]);

  return { status, coords, canAskAgain, refresh };
}
