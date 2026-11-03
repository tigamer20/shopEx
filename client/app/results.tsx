/**
 * Results (ARCHITECTURE §5): one card per list item with the chosen offer, approve toggle and
 * the "i" button ("See more options" sheet with the alternatives), demo-price banner, totals,
 * and a sticky "Approve all" → "Plan my route" CTA.
 */
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import type { Offer } from '@/api/types';
import { DemoPriceBanner, MoreOptionsSheet, ResultItemCard } from '@/components/flow';
import { AppText, Button, Card, EmptyState, ErrorBanner, Screen } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useSearchSession } from '@/search/SearchSession';
import { chosenOffer, matchedIndexes } from '@/search/selection';
import { useTheme } from '@/theme';
import { formatPrice } from '@/utils/format';
import { MAX_ITINERARY_STORES } from '@/utils/maps';

export default function ResultsScreen() {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();
  const router = useRouter();
  const { result, selection, approved, chooseOffer, setApproved, approveAll, allApproved, chosenStores, chosenTotal } =
    useSearchSession();
  const [sheetIndex, setSheetIndex] = useState<number | null>(null);

  if (!result) {
    return (
      <Screen edges={['left', 'right', 'bottom']}>
        <EmptyState
          icon="pricetags-outline"
          title={t('results.empty_title')}
          message={t('results.empty_message')}
          actionLabel={t('results.new_list')}
          onAction={() => router.replace('/list/edit')}
        />
      </Screen>
    );
  }

  const matched = matchedIndexes(result);
  const approvedCount = matched.filter((index) => approved[index] === true).length;
  const tooManyStores = chosenStores.length > MAX_ITINERARY_STORES;
  const sheetItem = sheetIndex === null ? null : (result.results[sheetIndex] ?? null);

  const choose = (offer: Offer) => {
    if (sheetIndex !== null) {
      chooseOffer(sheetIndex, offer);
      // Picking an option explicitly counts as approving that item.
      setApproved(sheetIndex, true);
    }
    setSheetIndex(null);
  };

  let footer;
  if (matched.length === 0) {
    footer = (
      <Button label={t('common.actions.edit')} icon="create-outline" size="lg" fullWidth onPress={() => router.back()} />
    );
  } else if (allApproved) {
    footer = (
      <>
        {tooManyStores ? (
          <ErrorBanner
            message={t('results.too_many_stores', { count: chosenStores.length, max: MAX_ITINERARY_STORES })}
          />
        ) : null}
        <Button
          label={t('results.plan_route')}
          icon="navigate"
          size="lg"
          fullWidth
          disabled={tooManyStores}
          onPress={() => router.push('/itinerary')}
        />
      </>
    );
  } else {
    footer = (
      <>
        <AppText variant="caption" align="center">
          {t('results.approve_hint')}
        </AppText>
        <Button label={t('results.approve_all')} icon="checkmark-done" size="lg" fullWidth onPress={approveAll} />
      </>
    );
  }

  return (
    <Screen edges={['left', 'right', 'bottom']} background="surface" footer={footer}>
      {result.prices_are_demo ? <DemoPriceBanner /> : null}

      {matched.length === 0 ? (
        <ErrorBanner message={t('results.no_matches')} />
      ) : (
        <Card style={{ gap: theme.spacing.sm }}>
          <View style={[styles.row, { gap: theme.spacing.md }]}>
            <AppText variant="subtitle" style={styles.flex}>
              {t('results.total')}
            </AppText>
            <AppText variant="title" accessibilityLiveRegion="polite">
              {formatPrice(chosenTotal, language)}
            </AppText>
          </View>
          <View style={[styles.row, { gap: theme.spacing.md }]}>
            <AppText variant="caption" style={styles.flex}>
              {t('results.stores_count', { count: chosenStores.length })}
            </AppText>
            <AppText variant="label" color={allApproved ? 'success' : 'textMuted'}>
              {t('results.approved_count', { approved: approvedCount, total: matched.length })}
            </AppText>
          </View>
        </Card>
      )}

      {result.results.map((item, index) => (
        <ResultItemCard
          // Results keep the request order; the index is the item's identity in the session.
          key={index}
          item={item}
          chosen={chosenOffer(result, selection, index)}
          approved={approved[index] === true}
          onToggleApproved={() => setApproved(index, approved[index] !== true)}
          onMoreOptions={() => setSheetIndex(index)}
        />
      ))}

      {matched.length > 0 ? (
        // Store names, addresses and positions come from OpenStreetMap (ODbL attribution).
        <AppText variant="small" align="center">
          {t('common.osm_attribution')}
        </AppText>
      ) : null}

      <MoreOptionsSheet
        item={sheetItem}
        chosen={sheetIndex === null ? null : chosenOffer(result, selection, sheetIndex)}
        onChoose={choose}
        onClose={() => setSheetIndex(null)}
      />
    </Screen>
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
});
