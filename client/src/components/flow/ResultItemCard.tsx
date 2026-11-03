import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, View } from 'react-native';

import type { ItemResult, Offer } from '@/api/types';
import { AppText, Card, IconButton } from '@/components/ui';
import { isTranslationKey, useT } from '@/i18n';
import { useTheme } from '@/theme';

import { OfferDetails } from './OfferDetails';

export interface ResultItemCardProps {
  item: ItemResult;
  /** The offer currently chosen for this item (cheapest by default). */
  chosen: Offer | null;
  approved: boolean;
  onToggleApproved: () => void;
  /** Opens the "See more options" sheet. */
  onMoreOptions: () => void;
}

/**
 * One grocery-list item on the results screen: chosen offer, quantity × line total,
 * approve toggle and the "i" button; unmatched and brand-not-found messages.
 */
export function ResultItemCard({ item, chosen, approved, onToggleApproved, onMoreOptions }: ResultItemCardProps) {
  const theme = useTheme();
  const t = useT();
  const { query } = item;
  const messageKey = item.message_key && isTranslationKey(item.message_key) ? item.message_key : null;

  const header = (
    <View style={[styles.row, { gap: theme.spacing.sm }]}>
      <AppText variant="label" color="textMuted" numberOfLines={1} style={styles.flex}>
        {t('results.requested', { name: query.name })}
      </AppText>
      <AppText variant="label" color="textMuted">
        {t('results.quantity_short', { count: query.quantity })}
      </AppText>
    </View>
  );

  if (!chosen) {
    return (
      <Card style={{ gap: theme.spacing.sm }}>
        {header}
        <View style={[styles.row, { gap: theme.spacing.sm }]}>
          <Ionicons name="alert-circle-outline" size={20} color={theme.colors.danger} />
          <AppText variant="subtitle" color="danger">
            {t('results.not_found')}
          </AppText>
        </View>
        <AppText variant="caption">{t(messageKey ?? 'search.no_match')}</AppText>
      </Card>
    );
  }

  const brandNotFound = query.brand !== null && item.brand_matched === false;

  return (
    <Card
      style={{
        gap: theme.spacing.md,
        borderColor: approved ? theme.colors.success : theme.colors.border,
        borderWidth: approved ? 2 : StyleSheet.hairlineWidth,
      }}
    >
      {header}
      {brandNotFound ? (
        <View
          style={[
            styles.row,
            styles.notice,
            { gap: theme.spacing.sm, padding: theme.spacing.sm, borderRadius: theme.radius.sm, backgroundColor: theme.colors.surface },
          ]}
        >
          <Ionicons name="information-circle-outline" size={18} color={theme.colors.warning} />
          <View style={styles.flex}>
            <AppText variant="small" color="text">
              {t('results.requested_brand', { brand: query.brand ?? '' })}
            </AppText>
            <AppText variant="small">{t(messageKey ?? 'search.brand_not_found')}</AppText>
          </View>
        </View>
      ) : null}
      <OfferDetails offer={chosen} quantity={query.quantity} />
      <View style={[styles.row, { gap: theme.spacing.sm }]}>
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: approved }}
          accessibilityLabel={t('results.approve_item', { name: query.name })}
          onPress={onToggleApproved}
          hitSlop={4}
          style={({ pressed }) => [
            styles.row,
            styles.toggle,
            {
              gap: theme.spacing.xs,
              paddingHorizontal: theme.spacing.lg,
              borderRadius: theme.radius.pill,
              backgroundColor: approved ? theme.colors.success : theme.colors.surface,
              borderColor: approved ? theme.colors.success : theme.colors.border,
              opacity: pressed ? 0.85 : 1,
            },
          ]}
        >
          <Ionicons
            name={approved ? 'checkmark-circle' : 'ellipse-outline'}
            size={20}
            color={approved ? theme.colors.onPrimary : theme.colors.text}
          />
          <AppText variant="label" style={{ color: approved ? theme.colors.onPrimary : theme.colors.text }}>
            {approved ? t('results.approved') : t('results.approve')}
          </AppText>
        </Pressable>
        <View style={styles.flex} />
        <IconButton
          icon="information-circle-outline"
          variant="tonal"
          accessibilityLabel={t('results.see_more_for', { name: query.name })}
          onPress={onMoreOptions}
        />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  flex: {
    flex: 1,
  },
  notice: {
    alignItems: 'flex-start',
  },
  toggle: {
    minHeight: 40,
    borderWidth: 1,
  },
});
