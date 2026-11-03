/**
 * Catalog browse (ARCHITECTURE §5): debounced search, section chips, filter sheet and
 * paginated offers around the user's position (`GET /catalog/offers`).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, ScrollView, StyleSheet, View } from 'react-native';

import { fetchOffers, fetchSections, isAbortError } from '@/api/client';
import type { Offer, Section } from '@/api/types';
import { useAuth } from '@/auth';
import { DemoPriceBanner, FilterSheet, LocationNotice, OfferCard, SearchBox } from '@/components/flow';
import { countActiveFilters, EMPTY_FILTERS, toOffersQuery, type BrowseFilters } from '@/components/flow/filters';
import { AppText, Chip, EmptyState, ErrorBanner, Screen } from '@/components/ui';
import { useLocation } from '@/hooks/useLocation';
import { useLanguage, useT } from '@/i18n';
import { useTheme } from '@/theme';
import { errorMessageKey } from '@/utils/errors';

const SEARCH_DEBOUNCE_MS = 350;
const DEFAULT_RADIUS_KM = 10;

interface PageState {
  /** Query the page belongs to; differs from the current query while a new search loads. */
  key: string | null;
  items: Offer[];
  total: number;
  pricesAreDemo: boolean;
  error: unknown;
  loadingMore: boolean;
  moreError: unknown;
}

const EMPTY_PAGE: PageState = {
  key: null,
  items: [],
  total: 0,
  pricesAreDemo: false,
  error: null,
  loadingMore: false,
  moreError: null,
};

export default function BrowseScreen() {
  const theme = useTheme();
  const t = useT();
  const { language } = useLanguage();
  const { user } = useAuth();
  const location = useLocation();
  const defaultRadiusKm = user?.search_radius_km ?? DEFAULT_RADIUS_KM;

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [section, setSection] = useState<string | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [filters, setFilters] = useState<BrowseFilters>(EMPTY_FILTERS);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [sheetKey, setSheetKey] = useState(0);
  const [page, setPage] = useState<PageState>(EMPTY_PAGE);
  const [reloadCount, setReloadCount] = useState(0);
  const moreRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    const controller = new AbortController();
    fetchSections({ signal: controller.signal }).then(setSections, () => {
      // Sections are optional: the "All" chip still works.
    });
    return () => controller.abort();
  }, []);

  const lat = location.coords?.lat;
  const lon = location.coords?.lon;
  const params = useMemo(
    () =>
      lat === undefined || lon === undefined
        ? null
        : toOffersQuery(filters, { lat, lon, q: debouncedQuery, section, defaultRadiusKm }),
    [lat, lon, filters, debouncedQuery, section, defaultRadiusKm],
  );
  const paramsKey = params ? JSON.stringify(params) : null;

  useEffect(() => {
    if (!params || paramsKey === null) {
      return undefined;
    }
    const controller = new AbortController();
    moreRequest.current?.abort();
    fetchOffers(params, { signal: controller.signal }).then(
      (response) =>
        setPage({
          ...EMPTY_PAGE,
          key: paramsKey,
          items: response.items,
          total: response.total,
          pricesAreDemo: response.prices_are_demo,
        }),
      (error: unknown) => {
        if (!isAbortError(error)) {
          setPage({ ...EMPTY_PAGE, key: paramsKey, error });
        }
      },
    );
    return () => controller.abort();
  }, [params, paramsKey, reloadCount]);

  useEffect(() => () => moreRequest.current?.abort(), []);

  const loading = paramsKey !== null && page.key !== paramsKey;
  const current = loading ? EMPTY_PAGE : page;
  const hasMore = current.items.length < current.total;

  const retry = () => {
    setPage(EMPTY_PAGE);
    setReloadCount((count) => count + 1);
  };

  const loadMore = () => {
    if (!params || loading || page.loadingMore || page.error || !hasMore) {
      return;
    }
    const key = paramsKey;
    const controller = new AbortController();
    moreRequest.current = controller;
    setPage((previous) => ({ ...previous, loadingMore: true, moreError: null }));
    fetchOffers({ ...params, offset: page.items.length }, { signal: controller.signal }).then(
      (response) =>
        setPage((previous) => {
          if (previous.key !== key) {
            return previous;
          }
          const seen = new Set(previous.items.map((offer) => offer.price_id));
          const fresh = response.items.filter((offer) => !seen.has(offer.price_id));
          // An empty page means the total shrank meanwhile (daily refresh): stop paging.
          const total = fresh.length === 0 ? previous.items.length : response.total;
          return { ...previous, items: [...previous.items, ...fresh], total, loadingMore: false };
        }),
      (error: unknown) =>
        setPage((previous) =>
          previous.key === key
            ? { ...previous, loadingMore: false, moreError: isAbortError(error) ? null : error }
            : previous,
        ),
    );
  };

  const knownChains = useMemo(() => {
    const names = new Set(current.items.map((offer) => offer.store.chain ?? offer.store.name));
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [current.items]);

  const activeFilters = countActiveFilters(filters);

  const openFilters = () => {
    setSheetKey((key) => key + 1);
    setSheetVisible(true);
  };

  const header = (
    <View style={{ gap: theme.spacing.md, paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.lg }}>
      <AppText variant="title">{t('browse.title')}</AppText>
      <SearchBox
        value={query}
        onChangeText={setQuery}
        placeholder={t('browse.search_placeholder')}
        accessibilityLabel={t('browse.search_label')}
      />
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        accessibilityLabel={t('browse.sections_label')}
        contentContainerStyle={{ gap: theme.spacing.sm, paddingBottom: theme.spacing.sm }}
      >
        <Chip
          icon="options-outline"
          label={activeFilters > 0 ? t('browse.filters_active', { count: activeFilters }) : t('browse.filters')}
          accessibilityLabel={t('browse.open_filters')}
          selected={activeFilters > 0}
          onPress={openFilters}
        />
        <Chip label={t('browse.all_sections')} selected={section === null} onPress={() => setSection(null)} />
        {sections.map((item) => (
          <Chip
            key={item.id}
            label={language === 'fr' ? item.name_fr : item.name_en}
            selected={section === item.id}
            onPress={() => setSection(section === item.id ? null : item.id)}
          />
        ))}
      </ScrollView>
    </View>
  );

  const listHeader =
    current.items.length > 0 ? (
      <View style={{ gap: theme.spacing.md }}>
        {current.pricesAreDemo ? <DemoPriceBanner /> : null}
        <AppText variant="label" color="textMuted" accessibilityLiveRegion="polite">
          {t('browse.results_count', { count: current.total })}
        </AppText>
        {/* Store names, addresses and positions come from OpenStreetMap (ODbL attribution). */}
        <AppText variant="small">{t('common.osm_attribution')}</AppText>
      </View>
    ) : undefined;

  let emptyContent;
  if (!params) {
    emptyContent = (
      <LocationNotice status={location.status} reasonKey="browse.location_needed" onRetry={() => void location.refresh()} />
    );
  } else if (loading) {
    emptyContent = (
      <ActivityIndicator
        size="large"
        color={theme.colors.primary}
        accessibilityLabel={t('common.loading')}
        style={{ marginTop: theme.spacing.xxl }}
      />
    );
  } else if (current.error) {
    emptyContent = <ErrorBanner message={t(errorMessageKey(current.error))} onRetry={retry} />;
  } else {
    emptyContent = <EmptyState icon="search-outline" title={t('browse.empty_title')} message={t('browse.empty_message')} />;
  }

  let footer;
  if (current.loadingMore) {
    footer = <ActivityIndicator color={theme.colors.primary} accessibilityLabel={t('common.loading')} />;
  } else if (current.moreError) {
    footer = <ErrorBanner message={t(errorMessageKey(current.moreError))} onRetry={loadMore} />;
  }

  return (
    <Screen scroll={false} padded={false}>
      {header}
      <FlatList
        data={current.items}
        keyExtractor={(offer) => String(offer.price_id)}
        renderItem={({ item }) => <OfferCard offer={item} />}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={emptyContent}
        ListFooterComponent={footer}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        contentContainerStyle={[styles.list, { gap: theme.spacing.md, padding: theme.spacing.lg }]}
      />
      <FilterSheet
        key={sheetKey}
        visible={sheetVisible}
        value={filters}
        defaultRadiusKm={defaultRadiusKm}
        knownChains={knownChains}
        onApply={(next) => {
          setFilters(next);
          setSheetVisible(false);
        }}
        onClose={() => setSheetVisible(false)}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    flexGrow: 1,
  },
});
