/**
 * Home: greeting, location chip, the big "New grocery list" CTA, the bookmarks carousel
 * and the most recent lists (ARCHITECTURE §5).
 */
import { useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import type { GroceryListSummary } from '@/api/types';
import { useAuth } from '@/auth';
import { BookmarkCard } from '@/components/home/BookmarkCard';
import { LocationChip } from '@/components/home/LocationChip';
import { NewListCta } from '@/components/home/NewListCta';
import { ListCard } from '@/components/lists/ListCard';
import { useGroceryLists } from '@/components/lists/useGroceryLists';
import { AppText, EmptyState, ErrorBanner, Logo, Screen, SectionHeader } from '@/components/ui';
import { useLocation } from '@/hooks/useLocation';
import { useT } from '@/i18n';
import { useSearchSession } from '@/search/SearchSession';
import { useTheme } from '@/theme';
import { errorMessageKey } from '@/utils/errors';

const RECENT_LIMIT = 5;

export default function HomeScreen() {
  const theme = useTheme();
  const t = useT();
  const router = useRouter();
  const { user } = useAuth();
  const location = useLocation();
  const refreshLocation = location.refresh;
  const { lists, bookmarks, loading, refreshing, error, refresh, setBookmarked } = useGroceryLists();
  const [actionError, setActionError] = useState<unknown>(null);
  const resetSearch = useSearchSession().reset;

  // A new list starts empty: drop any draft or saved-list id left by an earlier search, so
  // searching the new list never overwrites a list from the history.
  const startNewList = useCallback(() => {
    resetSearch();
    router.push('/list/edit');
  }, [resetSearch, router]);

  const openList = useCallback(
    (list: GroceryListSummary) => router.push({ pathname: '/list/edit', params: { listId: String(list.id) } }),
    [router],
  );

  const toggleBookmark = useCallback(
    (list: GroceryListSummary) => {
      setActionError(null);
      setBookmarked(list.id, !list.bookmarked).catch(setActionError);
    },
    [setBookmarked],
  );

  const onRefresh = useCallback(() => {
    setActionError(null);
    void refresh();
    void refreshLocation();
  }, [refresh, refreshLocation]);

  const recent = lists.slice(0, RECENT_LIMIT);
  const shownError = actionError ?? error;

  return (
    <Screen
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />}
      contentContainerStyle={{ gap: theme.spacing.xl }}
    >
      <View style={{ gap: theme.spacing.md }}>
        <Logo size="sm" style={styles.logo} />
        <View style={{ gap: theme.spacing.xs }}>
          <AppText variant="title">
            {user ? t('home.greeting', { name: user.display_name }) : t('home.greeting_anonymous')}
          </AppText>
          <AppText variant="caption">{t('home.tagline')}</AppText>
        </View>
        <LocationChip location={location} radiusKm={user?.search_radius_km ?? null} />
      </View>

      <NewListCta onPress={startNewList} />

      {shownError ? (
        <ErrorBanner message={t(errorMessageKey(shownError))} onRetry={actionError ? undefined : () => void refresh()} />
      ) : null}

      <View style={{ gap: theme.spacing.md }}>
        <SectionHeader title={t('home.bookmarks')} />
        {loading ? null : bookmarks.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            // Bleed to the screen edges so cards scroll under the page padding.
            style={{ marginHorizontal: -theme.spacing.lg }}
            contentContainerStyle={{ gap: theme.spacing.md, paddingHorizontal: theme.spacing.lg, paddingVertical: 2 }}
          >
            {bookmarks.map((list) => (
              <BookmarkCard key={list.id} list={list} onPress={openList} />
            ))}
          </ScrollView>
        ) : (
          <AppText variant="caption">{t('home.bookmarks_empty')}</AppText>
        )}
      </View>

      <View style={{ gap: theme.spacing.md }}>
        <SectionHeader
          title={t('home.recent_lists')}
          actionLabel={lists.length > RECENT_LIMIT ? t('common.actions.see_all') : undefined}
          onAction={() => router.push('/lists')}
        />
        {loading ? (
          <ActivityIndicator color={theme.colors.primary} accessibilityLabel={t('common.loading')} />
        ) : recent.length > 0 ? (
          recent.map((list) => (
            <ListCard key={list.id} list={list} onOpen={openList} onToggleBookmark={toggleBookmark} />
          ))
        ) : (
          <EmptyState icon="receipt-outline" title={t('home.recent_empty_title')} message={t('home.recent_empty_body')} />
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  logo: {
    alignItems: 'flex-start',
  },
});
