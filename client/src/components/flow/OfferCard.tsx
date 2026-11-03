import { StyleSheet, View } from 'react-native';

import type { Offer } from '@/api/types';
import { AppText, Badge, Card } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';
import { formatDistance, formatPrice, formatUnitPrice } from '@/utils/format';

import { formatSize, productName } from './offerText';

export interface OfferCardProps {
  offer: Offer;
}

/** Catalog offer: product, brand, size, store, distance, price, unit price and sale badge. */
export function OfferCard({ offer }: OfferCardProps) {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();

  const name = productName(offer.product, language);
  const size = formatSize(offer.product, language);
  const price = formatPrice(offer.price, language);
  const distance = formatDistance(offer.store.distance_km, language);

  return (
    <Card
      accessibilityLabel={t('search.offer.accessibility', {
        product: name,
        brand: offer.product.brand,
        size,
        price,
        store: offer.store.name,
        distance,
      })}
    >
      <View style={[styles.row, { gap: theme.spacing.md }]}>
        <View style={[styles.main, { gap: theme.spacing.xs }]}>
          {offer.on_sale ? <Badge label={t('search.offer.on_sale')} tone="sale" icon="pricetag" /> : null}
          <AppText variant="subtitle" numberOfLines={2}>
            {name}
          </AppText>
          <AppText variant="caption" numberOfLines={1}>
            {t('search.offer.brand_size', { brand: offer.product.brand, size })}
          </AppText>
          <AppText variant="caption" numberOfLines={1}>
            {t('search.offer.store_at_distance', { store: offer.store.name, distance })}
          </AppText>
          {offer.product.tags.length > 0 ? (
            <View style={[styles.tags, { gap: theme.spacing.xs }]}>
              {offer.product.tags.map((tag) => (
                <Badge key={tag} label={t(`search.tags.${tag}`)} />
              ))}
            </View>
          ) : null}
        </View>
        <View style={[styles.prices, { gap: theme.spacing.xs }]}>
          <AppText variant="heading" color={offer.on_sale ? 'badgeSale' : 'text'}>
            {price}
          </AppText>
          {offer.on_sale ? (
            <AppText variant="small" style={styles.strike}>
              {formatPrice(offer.regular_price, language)}
            </AppText>
          ) : null}
          <AppText variant="small">{formatUnitPrice(offer.unit_price, offer.unit_price_unit, language)}</AppText>
        </View>
      </View>
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
  tags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  prices: {
    alignItems: 'flex-end',
  },
  strike: {
    textDecorationLine: 'line-through',
  },
});
