import { useState } from 'react';
import { ScrollView, StyleSheet, Switch, View } from 'react-native';

import { DIETARY_TAGS, SORT_OPTIONS } from '@/api/types';
import { AppText, BottomSheet, Button, Chip, TextField } from '@/components/ui';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';

import {
  EMPTY_FILTERS,
  isPriceRangeValid,
  parsePriceInput,
  priceToInput,
  RADIUS_CHOICES,
  toggleTag,
  type BrowseFilters,
} from './filters';
import { MAX_BRAND_LENGTH } from './listItems';

export interface FilterSheetProps {
  visible: boolean;
  value: BrowseFilters;
  /** The user's default radius (km), shown as the "My radius" choice. */
  defaultRadiusKm: number;
  /** Chains seen in the results so far, offered as quick choices. */
  knownChains: readonly string[];
  onApply: (filters: BrowseFilters) => void;
  onClose: () => void;
}

/** Browse filters: price range, brand, chain, dietary tags, on-sale, distance and sort. */
export function FilterSheet({ visible, value, defaultRadiusKm, knownChains, onApply, onClose }: FilterSheetProps) {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();

  // The draft starts from the applied filters; the parent remounts the sheet (new `key`) on
  // each opening so cancelled edits are dropped.
  const [draft, setDraft] = useState<BrowseFilters>(value);
  const [minText, setMinText] = useState(() => priceToInput(value.minPrice, language));
  const [maxText, setMaxText] = useState(() => priceToInput(value.maxPrice, language));

  const minPrice = parsePriceInput(minText);
  const maxPrice = parsePriceInput(maxText);
  const pricesParse = minPrice !== 'invalid' && maxPrice !== 'invalid';
  const rangeValid = pricesParse && isPriceRangeValid({ minPrice, maxPrice });
  const canApply = pricesParse && rangeValid;

  const update = (patch: Partial<BrowseFilters>) => setDraft((previous) => ({ ...previous, ...patch }));

  const apply = () => {
    if (minPrice === 'invalid' || maxPrice === 'invalid' || !rangeValid) {
      return;
    }
    onApply({ ...draft, brand: draft.brand.trim(), chain: draft.chain.trim(), minPrice, maxPrice });
  };

  const resetAll = () => {
    setDraft(EMPTY_FILTERS);
    setMinText('');
    setMaxText('');
  };

  const gap = { gap: theme.spacing.sm };

  return (
    <BottomSheet
      visible={visible}
      onClose={onClose}
      title={t('browse.filters')}
      footer={
        <View style={[styles.footer, gap]}>
          <Button label={t('common.actions.reset')} variant="secondary" onPress={resetAll} style={styles.flex} />
          <Button label={t('common.actions.apply')} onPress={apply} disabled={!canApply} style={styles.flex} />
        </View>
      }
    >
      <View style={gap}>
        <AppText variant="subtitle">{t('browse.filter_sheet.sort')}</AppText>
        <View style={[styles.wrap, gap]}>
          {SORT_OPTIONS.map((sort) => (
            <Chip key={sort} label={t(`browse.sort.${sort}`)} selected={draft.sort === sort} onPress={() => update({ sort })} />
          ))}
        </View>
      </View>

      <View style={gap}>
        <AppText variant="subtitle">{t('browse.filter_sheet.price_range')}</AppText>
        <View style={[styles.footer, gap]}>
          <TextField
            label={t('browse.filter_sheet.min_price')}
            value={minText}
            onChangeText={setMinText}
            placeholder={t('browse.filter_sheet.price_placeholder')}
            keyboardType="decimal-pad"
            maxLength={9}
            error={minPrice === 'invalid' ? t('browse.filter_sheet.invalid_price') : null}
            containerStyle={styles.flex}
          />
          <TextField
            label={t('browse.filter_sheet.max_price')}
            value={maxText}
            onChangeText={setMaxText}
            placeholder={t('browse.filter_sheet.price_placeholder')}
            keyboardType="decimal-pad"
            maxLength={9}
            error={maxPrice === 'invalid' ? t('browse.filter_sheet.invalid_price') : null}
            containerStyle={styles.flex}
          />
        </View>
        {pricesParse && !rangeValid ? (
          <AppText variant="caption" color="danger" accessibilityRole="alert">
            {t('browse.filter_sheet.invalid_range')}
          </AppText>
        ) : null}
      </View>

      <TextField
        label={t('browse.filter_sheet.brand')}
        value={draft.brand}
        onChangeText={(brand) => update({ brand })}
        placeholder={t('browse.filter_sheet.brand_placeholder')}
        maxLength={MAX_BRAND_LENGTH}
        autoCorrect={false}
      />

      <View style={gap}>
        <TextField
          label={t('browse.filter_sheet.chain')}
          value={draft.chain}
          onChangeText={(chain) => update({ chain })}
          placeholder={t('browse.filter_sheet.chain_placeholder')}
          maxLength={MAX_BRAND_LENGTH}
          autoCorrect={false}
        />
        {knownChains.length > 0 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={gap}>
            {knownChains.map((chain) => (
              <Chip
                key={chain}
                label={chain}
                selected={draft.chain.trim().toLowerCase() === chain.toLowerCase()}
                onPress={() => update({ chain: draft.chain.trim().toLowerCase() === chain.toLowerCase() ? '' : chain })}
              />
            ))}
          </ScrollView>
        ) : null}
      </View>

      <View style={gap}>
        <AppText variant="subtitle">{t('browse.filter_sheet.tags')}</AppText>
        <View style={[styles.wrap, gap]}>
          {DIETARY_TAGS.map((tag) => (
            <Chip
              key={tag}
              label={t(`search.tags.${tag}`)}
              selected={draft.tags.includes(tag)}
              onPress={() => update({ tags: toggleTag(draft.tags, tag) })}
            />
          ))}
        </View>
      </View>

      <View style={[styles.switchRow, gap]}>
        <AppText variant="subtitle" style={styles.flex}>
          {t('browse.filter_sheet.on_sale_only')}
        </AppText>
        <Switch
          value={draft.onSaleOnly}
          onValueChange={(onSaleOnly) => update({ onSaleOnly })}
          accessibilityLabel={t('browse.filter_sheet.on_sale_only')}
          trackColor={{ true: theme.colors.primary, false: theme.colors.border }}
        />
      </View>

      <View style={gap}>
        <AppText variant="subtitle">{t('browse.filter_sheet.distance')}</AppText>
        <View style={[styles.wrap, gap]}>
          <Chip
            label={t('browse.filter_sheet.distance_default', { km: defaultRadiusKm })}
            selected={draft.radiusKm === null}
            onPress={() => update({ radiusKm: null })}
          />
          {RADIUS_CHOICES.map((km) => (
            <Chip
              key={km}
              label={t('browse.filter_sheet.distance_value', { km })}
              selected={draft.radiusKm === km}
              onPress={() => update({ radiusKm: km })}
            />
          ))}
        </View>
      </View>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  footer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  flex: {
    flex: 1,
  },
  wrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
