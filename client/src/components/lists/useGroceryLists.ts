/**
 * The signed-in user's saved lists (history + bookmarks), shared by Home and the Lists tab.
 * Reloads every time the screen gains focus, so lists saved by a search show up on return.
 */
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { deleteList, fetchLists, isAbortError, isApiError, updateList } from '@/api/client';
import type { GroceryListSummary } from '@/api/types';

export interface UseGroceryListsResult {
  /** Every list, most recently used first (server order). */
  lists: GroceryListSummary[];
  bookmarks: GroceryListSummary[];
  /** True only for the first load (nothing to show yet). */
  loading: boolean;
  /** True during a pull-to-refresh. */
  refreshing: boolean;
  /** Last load failure, or null. */
  error: unknown;
  /** Pull-to-refresh / retry. */
  refresh: () => Promise<void>;
  /** Optimistic star toggle; rolls back and rethrows on failure. */
  setBookmarked: (id: number, bookmarked: boolean) => Promise<void>;
  /** Deletes on the server, then drops the list locally. Rethrows on failure. */
  remove: (id: number) => Promise<void>;
}

export function useGroceryLists(): UseGroceryListsResult {
  const [lists, setLists] = useState<GroceryListSummary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const controller = useRef<AbortController | null>(null);

  const load = useCallback(async (): Promise<void> => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    try {
      const next = await fetchLists({}, { signal: current.signal });
      setLists(next);
      setError(null);
    } catch (caught) {
      if (!isAbortError(caught)) {
        setError(caught);
      }
    } finally {
      if (controller.current === current) {
        controller.current = null;
        setLoaded(true);
      }
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  useEffect(() => () => controller.current?.abort(), []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }, [load]);

  const setBookmarked = useCallback(async (id: number, bookmarked: boolean) => {
    const patch = (value: boolean) =>
      setLists((previous) => previous.map((list) => (list.id === id ? { ...list, bookmarked: value } : list)));
    patch(bookmarked);
    try {
      await updateList(id, { bookmarked });
    } catch (caught) {
      patch(!bookmarked);
      throw caught;
    }
  }, []);

  const remove = useCallback(async (id: number) => {
    try {
      await deleteList(id);
    } catch (caught) {
      // Already gone (deleted from another device): the outcome the user asked for.
      if (!(isApiError(caught) && caught.status === 404)) {
        throw caught;
      }
    }
    setLists((previous) => previous.filter((list) => list.id !== id));
  }, []);

  const bookmarks = useMemo(() => lists.filter((list) => list.bookmarked), [lists]);

  return {
    lists,
    bookmarks,
    loading: !loaded,
    refreshing,
    error,
    refresh,
    setBookmarked,
    remove,
  };
}
