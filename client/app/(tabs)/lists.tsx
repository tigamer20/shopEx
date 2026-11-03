/**
 * Lists tab: History / Bookmarks. Tap a list to reuse it in the editor, the star toggles the
 * bookmark, the trash button deletes after a confirmation (ARCHITECTURE §5).
 */
import { useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { GroceryListSummary } from '@/api/types';
import { ConfirmSheet } from '@/components/lists/ConfirmSheet';
import { ListCard } from '@/components/lists/ListCard';
import { SegmentedControl, type Segment } from '@/components/lists/SegmentedControl';
import { useGroceryLists } from '@/components/lists/useGroceryLists';
import { AppText, EmptyState, ErrorBanner } from '@/components/ui';
import { useT } from '@/i18n';
import { useSearchSession } from '@/search/SearchSession';
import { useTheme } from '@/theme';
import { errorMessageKey } from '@/utils/errors';

type ListsFilter = 'history' | 'bookmarks';

export default function ListsScreen() {
  const theme = useTheme();
  const t = useT();
  const router = useRouter();
  const { lists, bookmarks, loading, refreshing, error, refresh, setBookmarked, remove } = useGroceryLists();
  const [filter, setFilter] = useState<ListsFilter>('history');
  const [actionError, setActionError] = useState<unknown>(null);
  const [pendingDelete, setPendingDelete] = useState<GroceryListSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown>(null);

  const segments = useMemo<Segment<ListsFilter>[]>(
    () => [
      { value: 'history', label: t('lists.history') },
      { value: 'bookmarks', label: t('lists.bookmarks') },
    ],
    [t],
  );

  const { reset: resetSearch, listId: sessionListId, setListMeta } = useSearchSession();

  // Same rule as Home: a new list starts empty and without the saved-list id of an earlier
  // search, so searching it never overwrites (or 404s on a deleted) history entry.
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

  const askDelete = useCallback((list: GroceryListSummary) => {
    setDeleteError(null);
    setPendingDelete(list);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!pendingDelete) {
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      await remove(pendingDelete.id);
      if (sessionListId === pendingDelete.id) {
        // The draft in the search session pointed at this list: its next search saves a new one.
        setListMeta({ listId: null });
      }
      setPendingDelete(null);
    } catch (caught) {
      setDeleteError(caught);
    } finally {
      setDeleting(false);
    }
  }, [pendingDelete, remove, sessionListId, setListMeta]);

  const onRefresh = useCallback(() => {
    setActionError(null);
    void refresh();
  }, [refresh]);

  const data = filter === 'history' ? lists : bookmarks;
  const shownError = actionError ?? error;

  const empty = loading ? (
    <ActivityIndicator style={styles.loader} color={theme.colors.primary} accessibilityLabel={t('common.loading')} />
  ) : filter === 'history' ? (
    <EmptyState
      icon="receipt-outline"
      title={t('lists.empty_history_title')}
      message={t('lists.empty_history_body')}
      actionLabel={t('lists.new_list')}
      onAction={startNewList}
    />
  ) : (
    <EmptyState icon="star-outline" title={t('lists.empty_bookmarks_title')} message={t('lists.empty_bookmarks_body')} />
  );

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={[styles.fill, { backgroundColor: theme.colors.background }]}>
      <FlatList
        data={data}
        keyExtractor={(list) => String(list.id)}
        renderItem={({ item }) => (
          <ListCard list={item} onOpen={openList} onToggleBookmark={toggleBookmark} onDelete={askDelete} />
        )}
        contentContainerStyle={[styles.content, { padding: theme.spacing.lg, gap: theme.spacing.md }]}
        ListHeaderComponent={
          <View style={{ gap: theme.spacing.lg, marginBottom: theme.spacing.xs }}>
            <AppText variant="title">{t('lists.title')}</AppText>
            <SegmentedControl
              segments={segments}
              value={filter}
              onChange={setFilter}
              accessibilityLabel={t('lists.segments')}
            />
            {shownError ? (
              <ErrorBanner
                message={t(errorMessageKey(shownError))}
                onRetry={actionError ? undefined : () => void refresh()}
              />
            ) : null}
          </View>
        }
        ListEmptyComponent={empty}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.primary} />}
      />

      <ConfirmSheet
        visible={pendingDelete !== null}
        title={t('lists.delete_confirm_title')}
        message={t('lists.delete_confirm_body', { name: pendingDelete?.name ?? '' })}
        confirmLabel={t('common.actions.delete')}
        busy={deleting}
        error={deleteError ? t(errorMessageKey(deleteError)) : null}
        onConfirm={() => void confirmDelete()}
        onCancel={() => setPendingDelete(null)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
  },
  content: {
    flexGrow: 1,
  },
  loader: {
    marginTop: 32,
  },
});
