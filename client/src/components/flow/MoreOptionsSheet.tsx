import { StyleSheet, View } from 'react-native';

import type { ItemResult, Offer } from '@/api/types';
import { AppText, Badge, BottomSheet, Button, Card } from '@/components/ui';
import { useT } from '@/i18n';
import { useTheme } from '@/theme';

import { OfferDetails } from './OfferDetails';

export interface MoreOptionsSheetProps {
  /** The item whose options are shown; null hides the sheet. */
  item: ItemResult | null;
  chosen: Offer | null;
  onChoose: (offer: Offer) => void;
  onClose: () => void;
}

/**
 * "See more options": the cheapest offer and its (up to 2) alternatives; "Choose this one"
 * swaps the item's offer. The cheapest stays listed so the user can switch back.
 */
export function MoreOptionsSheet({ item, chosen, onChoose, onClose }: MoreOptionsSheetProps) {
  const theme = useTheme();
  const t = useT();
  const options = item?.best ? [item.best, ...item.alternatives] : [];

  return (
    <BottomSheet visible={item !== null} onClose={onClose} title={t('results.see_more')}>
      {item ? (
        <AppText variant="caption">
          {t('results.requested', { name: item.query.name })} · {t('results.quantity_short', { count: item.query.quantity })}
        </AppText>
      ) : null}
      {options.map((offer, index) => {
        const isChosen = chosen?.price_id === offer.price_id;
        return (
          <Card
            key={offer.price_id}
            style={{
              gap: theme.spacing.md,
              borderColor: isChosen ? theme.colors.primary : theme.colors.border,
              borderWidth: isChosen ? 2 : StyleSheet.hairlineWidth,
            }}
          >
            <View style={[styles.badges, { gap: theme.spacing.xs }]}>
              {index === 0 ? <Badge label={t('results.cheapest')} tone="success" icon="trending-down" /> : null}
              {isChosen ? <Badge label={t('results.current_choice')} tone="primary" icon="checkmark" /> : null}
            </View>
            <OfferDetails offer={offer} quantity={item?.query.quantity} />
            {isChosen ? null : (
              <Button label={t('results.choose_this')} variant="secondary" onPress={() => onChoose(offer)} />
            )}
          </Card>
        );
      })}
      {item && item.alternatives.length === 0 ? (
        <AppText variant="caption" align="center">
          {t('results.no_alternatives')}
        </AppText>
      ) : null}
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  badges: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
});
