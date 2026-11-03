/**
 * Itinerary (ARCHITECTURE §5): POST /itinerary with the chosen stores and travel mode, then a
 * Leaflet/OSM map, ordered stop cards with leg distance/time, totals, the estimate notice,
 * "Open in Google Maps" and "Done" (back home, search session cleared).
 */
import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Linking, StyleSheet, View } from 'react-native';

import { isAbortError, planItinerary } from '@/api/client';
import { TRAVEL_MODES, type ItineraryResponse, type TravelMode } from '@/api/types';
import { useAuth } from '@/auth';
import { LocationNotice, StopCard } from '@/components/flow';
import { purchasesByStore, type Purchase } from '@/components/flow/offerText';
import { ItineraryMap } from '@/components/map';
import { AppText, Button, Card, Chip, EmptyState, ErrorBanner, Screen, type IconName } from '@/components/ui';
import { useLocation } from '@/hooks/useLocation';
import { useLanguage, useT } from '@/i18n';
import { useSearchSession } from '@/search/SearchSession';
import { useTheme } from '@/theme';
import { errorMessageKey } from '@/utils/errors';
import { formatDistance, formatDuration } from '@/utils/format';
import { buildGoogleMapsUrl, isGoogleMapsUrl, MAX_ITINERARY_STORES } from '@/utils/maps';

const MODE_ICONS: Record<TravelMode, IconName> = {
  driving: 'car-outline',
  walking: 'walk-outline',
  cycling: 'bicycle-outline',
};

interface PlanState {
  /** Request the state belongs to; differs from the current request while it loads. */
  key: string;
  response: ItineraryResponse | null;
  error: unknown;
}

export default function ItineraryScreen() {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();
  const router = useRouter();
  const { user } = useAuth();
  const session = useSearchSession();
  const location = useLocation();

  // Snapshot of the approved choices: "Done" clears the session while this screen animates out.
  const [snapshot] = useState(() => ({
    result: session.result,
    selection: session.selection,
    stores: session.chosenStores,
    ready: session.allApproved,
  }));
  const [mode, setMode] = useState<TravelMode>(user?.travel_mode ?? 'driving');
  const [plan, setPlan] = useState<PlanState | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [openError, setOpenError] = useState(false);

  const lat = location.coords?.lat;
  const lon = location.coords?.lon;
  const canPlan = snapshot.ready && snapshot.stores.length > 0 && snapshot.stores.length <= MAX_ITINERARY_STORES;
  const requestKey =
    canPlan && lat !== undefined && lon !== undefined ? JSON.stringify([lat, lon, mode, attempt]) : null;

  useEffect(() => {
    if (requestKey === null || lat === undefined || lon === undefined) {
      return undefined;
    }
    const controller = new AbortController();
    planItinerary(
      { start: { lat, lon }, store_ids: snapshot.stores.map((store) => store.id), travel_mode: mode },
      { signal: controller.signal },
    ).then(
      (response) => setPlan({ key: requestKey, response, error: null }),
      (error: unknown) => {
        if (!isAbortError(error)) {
          setPlan({ key: requestKey, response: null, error });
        }
      },
    );
    return () => controller.abort();
  }, [requestKey, lat, lon, mode, snapshot]);

  const purchases = useMemo(
    () => (snapshot.result ? purchasesByStore(snapshot.result, snapshot.selection, language) : new Map<number, Purchase[]>()),
    [snapshot, language],
  );

  const start = useMemo(() => (lat !== undefined && lon !== undefined ? { lat, lon } : null), [lat, lon]);

  const finish = () => {
    session.reset();
    router.dismissTo('/');
  };

  if (!canPlan) {
    return (
      <Screen edges={['left', 'right', 'bottom']}>
        <EmptyState
          icon="map-outline"
          title={t('itinerary.empty_title')}
          message={t('itinerary.empty_message')}
          actionLabel={t('itinerary.back_to_results')}
          onAction={() => router.back()}
        />
      </Screen>
    );
  }

  const current = plan !== null && plan.key === requestKey ? plan : null;
  const loading = requestKey !== null && current === null;
  const itinerary = current?.response ?? null;

  const openInMaps = () => {
    if (!itinerary || !start) {
      return;
    }
    const url = isGoogleMapsUrl(itinerary.maps_url)
      ? itinerary.maps_url
      : buildGoogleMapsUrl(
          start,
          itinerary.stops.map((stop) => stop.store),
          mode,
        );
    setOpenError(false);
    Linking.openURL(url).catch(() => setOpenError(true));
  };

  return (
    <Screen
      edges={['left', 'right', 'bottom']}
      footer={
        <>
          {openError ? <ErrorBanner message={t('itinerary.open_maps_error')} /> : null}
          <Button
            label={t('itinerary.open_in_maps')}
            icon="navigate-outline"
            variant="secondary"
            fullWidth
            disabled={!itinerary}
            onPress={openInMaps}
          />
          <Button label={t('itinerary.done')} icon="checkmark" size="lg" fullWidth onPress={finish} />
        </>
      }
    >
      <View style={{ gap: theme.spacing.sm }}>
        <AppText variant="label">{t('itinerary.travel_mode_label')}</AppText>
        <View style={[styles.wrap, { gap: theme.spacing.sm }]}>
          {TRAVEL_MODES.map((value) => (
            <Chip
              key={value}
              icon={MODE_ICONS[value]}
              label={t(`itinerary.travel_mode.${value}`)}
              selected={mode === value}
              disabled={loading}
              onPress={() => setMode(value)}
            />
          ))}
        </View>
      </View>

      {!start ? (
        <LocationNotice status={location.status} reasonKey="itinerary.location_needed" onRetry={() => void location.refresh()} />
      ) : null}

      {loading ? (
        <View style={[styles.center, { gap: theme.spacing.md, paddingVertical: theme.spacing.xxl }]}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <AppText variant="caption" accessibilityLiveRegion="polite">
            {t('itinerary.planning')}
          </AppText>
        </View>
      ) : null}

      {current?.error ? (
        <ErrorBanner message={t(errorMessageKey(current.error))} onRetry={() => setAttempt((count) => count + 1)} />
      ) : null}

      {itinerary && start ? (
        <>
          <View style={{ gap: theme.spacing.xs }}>
            <ItineraryMap start={start} stops={itinerary.stops} geometry={itinerary.geometry} />
            <AppText variant="small" align="right">
              {t('common.osm_attribution')}
            </AppText>
          </View>

          {itinerary.routing_source === 'estimate' ? (
            <View
              style={[
                styles.notice,
                { gap: theme.spacing.sm, padding: theme.spacing.md, borderRadius: theme.radius.md, borderColor: theme.colors.warning },
              ]}
            >
              <AppText variant="caption" color="text">
                {t('itinerary.estimate_notice')}
              </AppText>
            </View>
          ) : null}

          <Card style={[styles.totals, { gap: theme.spacing.md }]}>
            <Total label={t('itinerary.total_distance')} value={formatDistance(itinerary.total_distance_km, language)} />
            <Total label={t('itinerary.total_duration')} value={formatDuration(itinerary.total_duration_min, language)} />
            <Total label={t('itinerary.stops')} value={String(itinerary.stops.length)} />
          </Card>

          {itinerary.stops.map((stop) => (
            <StopCard key={stop.store.id} stop={stop} purchases={purchases.get(stop.store.id) ?? []} />
          ))}
        </>
      ) : null}
    </Screen>
  );
}

function Total({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.total} accessible accessibilityLabel={`${label}: ${value}`}>
      <AppText variant="heading" align="center">
        {value}
      </AppText>
      <AppText variant="small" align="center">
        {label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  center: {
    alignItems: 'center',
  },
  notice: {
    borderWidth: 1,
  },
  totals: {
    flexDirection: 'row',
  },
  total: {
    flex: 1,
  },
});
