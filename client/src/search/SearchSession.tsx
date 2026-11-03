/**
 * Search state shared by `list/edit → results → itinerary` (ARCHITECTURE §5): the list being
 * searched, the server result, the offer chosen per item and the per-item approvals.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { isAbortError, searchPrices } from '@/api/client';
import type {
  GroceryItemInput,
  GroceryList,
  Offer,
  SearchFilters,
  SearchRequest,
  SearchResponse,
  Store,
} from '@/api/types';
import { useAuth } from '@/auth';

import {
  approveAllMatched,
  areAllApproved,
  chosenStoresOf,
  chosenTotalOf,
  defaultSelection,
  type Approvals,
  type OfferSelection,
} from './selection';

export type SearchStatus = 'idle' | 'loading' | 'success' | 'error';

export interface RunSearchOptions {
  radius_km?: number;
  filters?: SearchFilters;
  /** Defaults to true: the search is recorded in the user's history. */
  save_to_history?: boolean;
}

interface SessionState {
  items: GroceryItemInput[];
  /** History entry to update on the next search (null = a new list is created). */
  listId: number | null;
  listName: string;
  result: SearchResponse | null;
  /** Chosen offer per item index; defaults to the cheapest (`best`). */
  selection: OfferSelection;
  approved: Approvals;
  status: SearchStatus;
  error: unknown;
}

export interface SearchSessionValue extends SessionState {
  /** Replaces the items; any previous result becomes stale and is cleared. */
  setItems: (items: GroceryItemInput[]) => void;
  setListMeta: (meta: { listId?: number | null; listName?: string }) => void;
  /** Loads a saved list (history/bookmark) into the editor. */
  loadList: (list: GroceryList) => void;
  /** Calls POST /search with the current items; rejects with an ApiError on failure. */
  runSearch: (lat: number, lon: number, options?: RunSearchOptions) => Promise<SearchResponse>;
  chooseOffer: (itemIndex: number, offer: Offer) => void;
  setApproved: (itemIndex: number, approved: boolean) => void;
  approveAll: () => void;
  reset: () => void;
  /** Every matched item is approved (and there is at least one). */
  allApproved: boolean;
  /** Unique stores of the chosen offers, nearest first. */
  chosenStores: Store[];
  /** Σ chosen price × quantity. */
  chosenTotal: number;
}

const INITIAL_STATE: SessionState = {
  items: [],
  listId: null,
  listName: '',
  result: null,
  selection: {},
  approved: {},
  status: 'idle',
  error: null,
};

const CLEARED_RESULT: Pick<SessionState, 'result' | 'selection' | 'approved' | 'status' | 'error'> = {
  result: null,
  selection: {},
  approved: {},
  status: 'idle',
  error: null,
};

const SearchSessionContext = createContext<SearchSessionValue | null>(null);

export function SearchSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(INITIAL_STATE);
  const inFlight = useRef<AbortController | null>(null);
  const { token } = useAuth();

  const cancelInFlight = useCallback(() => {
    inFlight.current?.abort();
    inFlight.current = null;
  }, []);

  const reset = useCallback(() => {
    cancelInFlight();
    setState(INITIAL_STATE);
  }, [cancelInFlight]);

  // A signed-out (or different) user must never see the previous user's list.
  useEffect(() => {
    if (!token) {
      reset();
    }
  }, [token, reset]);

  useEffect(() => cancelInFlight, [cancelInFlight]);

  const setItems = useCallback((items: GroceryItemInput[]) => {
    setState((previous) => ({ ...previous, ...CLEARED_RESULT, items }));
  }, []);

  const setListMeta = useCallback((meta: { listId?: number | null; listName?: string }) => {
    setState((previous) => ({
      ...previous,
      listId: meta.listId === undefined ? previous.listId : meta.listId,
      listName: meta.listName ?? previous.listName,
    }));
  }, []);

  const loadList = useCallback((list: GroceryList) => {
    setState({ ...INITIAL_STATE, items: list.items, listId: list.id, listName: list.name });
  }, []);

  const { items, listId, listName } = state;

  const runSearch = useCallback(
    async (lat: number, lon: number, options: RunSearchOptions = {}): Promise<SearchResponse> => {
      cancelInFlight();
      const controller = new AbortController();
      inFlight.current = controller;
      setState((previous) => ({ ...previous, status: 'loading', error: null }));

      const request: SearchRequest = {
        lat,
        lon,
        items,
        save_to_history: options.save_to_history ?? true,
      };
      if (options.radius_km !== undefined) {
        request.radius_km = options.radius_km;
      }
      if (options.filters) {
        request.filters = options.filters;
      }
      if (listId !== null) {
        request.list_id = listId;
      }
      const trimmedName = listName.trim();
      if (trimmedName) {
        request.list_name = trimmedName;
      }

      try {
        const result = await searchPrices(request, { signal: controller.signal });
        if (inFlight.current === controller) {
          setState((previous) => ({
            ...previous,
            status: 'success',
            error: null,
            result,
            listId: result.list_id ?? previous.listId,
            selection: defaultSelection(result),
            approved: {},
          }));
        }
        return result;
      } catch (error) {
        if (!isAbortError(error) && inFlight.current === controller) {
          setState((previous) => ({ ...previous, status: 'error', error }));
        }
        throw error;
      } finally {
        if (inFlight.current === controller) {
          inFlight.current = null;
        }
      }
    },
    [cancelInFlight, items, listId, listName],
  );

  const chooseOffer = useCallback((itemIndex: number, offer: Offer) => {
    setState((previous) => ({ ...previous, selection: { ...previous.selection, [itemIndex]: offer } }));
  }, []);

  const setApproved = useCallback((itemIndex: number, approved: boolean) => {
    setState((previous) => ({ ...previous, approved: { ...previous.approved, [itemIndex]: approved } }));
  }, []);

  const approveAll = useCallback(() => {
    setState((previous) =>
      previous.result ? { ...previous, approved: approveAllMatched(previous.result) } : previous,
    );
  }, []);

  const allApproved = useMemo(() => areAllApproved(state.result, state.approved), [state.result, state.approved]);
  const chosenStores = useMemo(
    () => chosenStoresOf(state.result, state.selection),
    [state.result, state.selection],
  );
  const chosenTotal = useMemo(
    () => chosenTotalOf(state.result, state.selection),
    [state.result, state.selection],
  );

  const value = useMemo<SearchSessionValue>(
    () => ({
      ...state,
      setItems,
      setListMeta,
      loadList,
      runSearch,
      chooseOffer,
      setApproved,
      approveAll,
      reset,
      allApproved,
      chosenStores,
      chosenTotal,
    }),
    [
      state,
      setItems,
      setListMeta,
      loadList,
      runSearch,
      chooseOffer,
      setApproved,
      approveAll,
      reset,
      allApproved,
      chosenStores,
      chosenTotal,
    ],
  );

  return <SearchSessionContext.Provider value={value}>{children}</SearchSessionContext.Provider>;
}

export function useSearchSession(): SearchSessionValue {
  const context = useContext(SearchSessionContext);
  if (!context) {
    throw new Error('useSearchSession must be used inside <SearchSessionProvider>');
  }
  return context;
}
