import { StyleSheet, View } from 'react-native';

import type { Offer } from '@/api/types';
import { AppText, Badge } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';
import { formatDistance, formatPrice, formatUnitPrice } from '@/utils/format';

import { formatSize, productName } from './offerText';

export interface OfferDetailsProps {
  offer: Offer;
  /** Item quantity: shows "qty × price = total" when given. */
  quantity?: number;
}

/** Product name, brand + size, store + distance on the left; price block on the right. */
export function OfferDetails({ offer, quantity }: OfferDetailsProps) {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();
  const price = formatPrice(offer.price, language);

  return (
    <View style={[styles.row, { gap: theme.spacing.md }]}>
      <View style={[styles.main, { gap: theme.spacing.xs }]}>
        <AppText variant="subtitle" numberOfLines={2}>
          {productName(offer.product, language)}
        </AppText>
        <AppText variant="caption" numberOfLines={1}>
          {t('search.offer.brand_size', { brand: offer.product.brand, size: formatSize(offer.product, language) })}
        </AppText>
        <View style={[styles.storeRow, { gap: theme.spacing.xs }]}>
          <AppText variant="caption" color="text" numberOfLines={1} style={styles.shrink}>
            {t('search.offer.store_at_distance', {
              store: offer.store.name,
              distance: formatDistance(offer.store.distance_km, language),
            })}
          </AppText>
        </View>
      </View>
      <View style={[styles.prices, { gap: theme.spacing.xs }]}>
        {offer.on_sale ? <Badge label={t('search.offer.on_sale')} tone="sale" /> : null}
        <AppText variant="heading" color={offer.on_sale ? 'badgeSale' : 'text'}>
          {price}
        </AppText>
        {offer.on_sale ? (
          <AppText variant="small" style={styles.strike}>
            {t('search.offer.regular_price', { price: formatPrice(offer.regular_price, language) })}
          </AppText>
        ) : null}
        <AppText variant="small">{formatUnitPrice(offer.unit_price, offer.unit_price_unit, language)}</AppText>
        {quantity !== undefined ? (
          <AppText variant="label">
            {t('results.line_total', {
              quantity,
              price,
              total: formatPrice(Math.round(offer.price * quantity * 100) / 100, language),
            })}
          </AppText>
        ) : null}
      </View>
    </View>
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
  storeRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  shrink: {
    flexShrink: 1,
  },
  prices: {
    alignItems: 'flex-end',
  },
  strike: {
    textDecorationLine: 'line-through',
  },
});
