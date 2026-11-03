/**
 * List editor (ARCHITECTURE §5): name, items (name + favourite brand + quantity), quick-add
 * suggestions, reorder/remove, then "Find the best prices" → POST /search → /results.
 * `?listId=` reuses a saved list (history/bookmark). Items live in the search session so
 * they survive the round trip to the results screen.
 */
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';

import { fetchList, isAbortError } from '@/api/client';
import { useAuth } from '@/auth';
import { EditorItemRow, LocationNotice, QuantityStepper } from '@/components/flow';
import {
  addItem,
  makeItem,
  MAX_BRAND_LENGTH,
  MAX_ITEMS,
  MAX_LIST_NAME_LENGTH,
  MAX_NAME_LENGTH,
  moveItem,
  removeItemAt,
  setQuantityAt,
} from '@/components/flow/listItems';
import { AppText, Button, Card, Chip, EmptyState, ErrorBanner, Screen, SectionHeader, TextField } from '@/components/ui';
import { useLocation } from '@/hooks/useLocation';
import { useT, type TranslationKey } from '@/i18n';
import { useSearchSession } from '@/search/SearchSession';
import { useTheme } from '@/theme';
import { errorMessageKey } from '@/utils/errors';

const SUGGESTIONS = [
  'milk',
  'eggs',
  'bread',
  'butter',
  'bananas',
  'apples',
  'cheese',
  'chicken',
  'rice',
  'pasta',
  'coffee',
  'yogurt',
  'tomatoes',
  'cereal',
] as const;

/** Parses `?listId=`: a positive integer, else null. */
function parseListId(raw: string | string[] | undefined): number | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value || !/^\d{1,10}$/.test(value)) {
    return null;
  }
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

export default function ListEditorScreen() {
  const theme = useTheme();
  const t = useT();
  const router = useRouter();
  const { user } = useAuth();
  const session = useSearchSession();
  const location = useLocation();
  const { listId: listIdParam } = useLocalSearchParams<{ listId?: string }>();
  const requestedListId = parseListId(listIdParam);

  const [name, setName] = useState('');
  const [brand, setBrand] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [formError, setFormError] = useState<TranslationKey | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [reloadCount, setReloadCount] = useState(0);
  const handledListId = useRef<number | null>(null);

  const { items, listName, setItems, setListMeta, loadList, runSearch } = session;
  const sessionListId = session.listId;

  // Reuse a saved list once per requested id (the session may already hold it, e.g. after
  // coming back from the results screen).
  useEffect(() => {
    if (requestedListId === null || handledListId.current === requestedListId) {
      return undefined;
    }
    handledListId.current = requestedListId;
    if (sessionListId === requestedListId) {
      return undefined;
    }
    const controller = new AbortController();
    fetchList(requestedListId, { signal: controller.signal }).then(
      (list) => {
        loadList(list);
        setLoadError(null);
      },
      (error: unknown) => {
        if (!isAbortError(error)) {
          handledListId.current = null;
          setLoadError(error);
        }
      },
    );
    return () => {
      // An aborted load may be retried (e.g. React's development double-mount).
      if (handledListId.current === requestedListId) {
        handledListId.current = null;
      }
      controller.abort();
    };
  }, [requestedListId, sessionListId, loadList, reloadCount]);

  const add = (itemName: string, itemBrand: string | null, itemQuantity: number): boolean => {
    const item = makeItem(itemName, itemBrand, itemQuantity);
    if (!item) {
      setFormError('editor.item_name_required');
      return false;
    }
    const { items: next, outcome } = addItem(items, item);
    if (outcome === 'full') {
      setFormError('editor.too_many_items');
      return false;
    }
    setFormError(null);
    setItems(next);
    return true;
  };

  const submitForm = () => {
    if (add(name, brand, quantity)) {
      setName('');
      setBrand('');
      setQuantity(1);
    }
  };

  const findPrices = async () => {
    const coords = location.coords ?? (await location.refresh());
    if (!coords) {
      return;
    }
    try {
      await runSearch(coords.lat, coords.lon, { radius_km: user?.search_radius_km });
      router.push('/results');
    } catch {
      // The session exposes the error; aborted searches need no message.
    }
  };

  const searching = session.status === 'loading';
  const searchError = session.status === 'error' && !isAbortError(session.error) ? session.error : null;
  const missingLocation = !location.coords && location.status !== 'locating' && location.status !== 'granted';

  // A requested saved list is still on its way into the session.
  const loadingList = requestedListId !== null && sessionListId !== requestedListId && loadError === null;

  if (loadingList) {
    return (
      <Screen edges={['left', 'right', 'bottom']}>
        <View style={[styles.center, { gap: theme.spacing.md, paddingTop: theme.spacing.xxl }]}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <AppText variant="caption">{t('editor.loading_list')}</AppText>
        </View>
      </Screen>
    );
  }

  return (
    <Screen
      edges={['left', 'right', 'bottom']}
      footer={
        <>
          {searchError ? <ErrorBanner message={t(errorMessageKey(searchError))} /> : null}
          <Button
            label={searching ? t('editor.searching') : t('editor.find_prices')}
            icon="pricetags"
            size="lg"
            fullWidth
            loading={searching}
            disabled={items.length === 0 || searching}
            accessibilityLabel={t('editor.find_prices')}
            onPress={() => void findPrices()}
          />
        </>
      }
    >
      {loadError !== null ? (
        <ErrorBanner
          message={t(errorMessageKey(loadError))}
          onRetry={() => {
            setLoadError(null);
            setReloadCount((count) => count + 1);
          }}
        />
      ) : null}

      <TextField
        label={t('editor.list_name')}
        placeholder={t('editor.list_name_placeholder')}
        value={listName}
        onChangeText={(text) => setListMeta({ listName: text })}
        maxLength={MAX_LIST_NAME_LENGTH}
        returnKeyType="done"
      />

      <Card style={{ gap: theme.spacing.md }}>
        <AppText variant="heading">{t('editor.add_title')}</AppText>
        <TextField
          label={t('editor.item_name')}
          placeholder={t('editor.item_name_placeholder')}
          value={name}
          onChangeText={(text) => {
            setName(text);
            if (formError === 'editor.item_name_required') setFormError(null);
          }}
          maxLength={MAX_NAME_LENGTH}
          error={formError ? t(formError, { max: MAX_ITEMS }) : null}
          returnKeyType="next"
          onSubmitEditing={submitForm}
        />
        <TextField
          label={t('editor.brand')}
          placeholder={t('editor.brand_placeholder')}
          value={brand}
          onChangeText={setBrand}
          maxLength={MAX_BRAND_LENGTH}
          autoCorrect={false}
          returnKeyType="done"
          onSubmitEditing={submitForm}
        />
        <View style={[styles.row, { gap: theme.spacing.md }]}>
          <View style={[styles.flex, { gap: theme.spacing.xs }]}>
            <AppText variant="label">{t('editor.quantity')}</AppText>
            <QuantityStepper
              value={quantity}
              onChange={setQuantity}
              accessibilityLabel={t('editor.quantity_value', { count: quantity })}
            />
          </View>
          <Button label={t('editor.add_item')} icon="add" onPress={submitForm} />
        </View>
      </Card>

      <View style={{ gap: theme.spacing.sm }}>
        <SectionHeader title={t('editor.suggestions_title')} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: theme.spacing.sm }}>
          {SUGGESTIONS.map((key) => {
            const label = t(`editor.suggestions.${key}`);
            return (
              <Chip
                key={key}
                icon="add"
                label={label}
                accessibilityLabel={t('editor.suggestion_label', { name: label })}
                onPress={() => add(label, null, 1)}
              />
            );
          })}
        </ScrollView>
      </View>

      <View style={{ gap: theme.spacing.md }}>
        <SectionHeader title={t('editor.items_title', { count: items.length })} />
        {items.length === 0 ? (
          <EmptyState icon="basket-outline" title={t('editor.empty_title')} message={t('editor.empty_message')} />
        ) : (
          items.map((item, index) => (
            <EditorItemRow
              key={`${index}-${item.name}-${item.brand ?? ''}`}
              item={item}
              isFirst={index === 0}
              isLast={index === items.length - 1}
              onQuantityChange={(value) => setItems(setQuantityAt(items, index, value))}
              onMove={(delta) => setItems(moveItem(items, index, delta))}
              onRemove={() => setItems(removeItemAt(items, index))}
            />
          ))
        )}
      </View>

      {missingLocation ? (
        <LocationNotice status={location.status} reasonKey="editor.location_needed" onRetry={() => void location.refresh()} />
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'flex-end',
  },
  flex: {
    flex: 1,
  },
  center: {
    alignItems: 'center',
  },
});
