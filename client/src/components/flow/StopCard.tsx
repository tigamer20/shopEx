import { StyleSheet, View } from 'react-native';

import type { ItineraryStop } from '@/api/types';
import { AppText, Card } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';
import { formatDistance, formatDuration } from '@/utils/format';

import { storeAddress, type Purchase } from './offerText';

export interface StopCardProps {
  stop: ItineraryStop;
  purchases: readonly Purchase[];
}

/** One itinerary stop: order badge, store, leg distance/time, arrival and what to buy there. */
export function StopCard({ stop, purchases }: StopCardProps) {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();
  const address = storeAddress(stop.store, language);

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <View style={[styles.row, { gap: theme.spacing.md }]}>
        <View
          accessible
          accessibilityLabel={t('itinerary.stop_label', { order: stop.order })}
          style={[styles.badge, { backgroundColor: theme.colors.primary, borderRadius: theme.radius.pill }]}
        >
          <AppText variant="subtitle" style={{ color: theme.colors.onPrimary, fontWeight: theme.fontWeight.heavy }}>
            {stop.order}
          </AppText>
        </View>
        <View style={[styles.main, { gap: theme.spacing.xs }]}>
          <AppText variant="subtitle" numberOfLines={2}>
            {stop.store.name}
          </AppText>
          {address ? (
            <AppText variant="caption" numberOfLines={2}>
              {address}
            </AppText>
          ) : null}
          <AppText variant="label">
            {t('itinerary.leg', {
              distance: formatDistance(stop.leg_distance_km, language),
              duration: formatDuration(stop.leg_duration_min, language),
            })}
          </AppText>
          <AppText variant="small">
            {t('itinerary.arrival', { duration: formatDuration(stop.arrival_min, language) })}
          </AppText>
        </View>
      </View>
      {purchases.length > 0 ? (
        <View style={[{ gap: theme.spacing.xs, padding: theme.spacing.md, borderRadius: theme.radius.md, backgroundColor: theme.colors.surface }]}>
          <AppText variant="label">{t('itinerary.to_buy')}</AppText>
          {purchases.map((purchase) => (
            <AppText key={purchase.itemIndex} variant="caption" color="text">
              {t('itinerary.item_line', { quantity: purchase.quantity, name: purchase.name })}
            </AppText>
          ))}
        </View>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  main: {
    flex: 1,
  },
  badge: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
