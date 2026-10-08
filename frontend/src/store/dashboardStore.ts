import { create } from "zustand";

import { fetchMarketCoins, fetchTopByVolume } from "../services/api/market.api";
import type { MarketCoin, MoverItem } from "../types/market";
import { toErrorMessage } from "../utils/apiErrors";
import { dedupe } from "../utils/dedupe";

/** How many coins feed the heatmap and the BTC/ETH asset lookup. */
export const HEATMAP_SIZE = 60;
/** Rows shown per Market Movers tab — deliberately concise. */
export const MOVERS_SIZE = 8;

interface Slice<T> {
  data: T;
  loading: boolean;
  error: string | null;
}

interface DashboardState {
  /** Top coins by market cap with 24h change — feeds the heatmap. */
  heatmap: Slice<MarketCoin[]>;
  /** Highest 24h volume — backed by the existing /market/top/volume. */
  volume: Slice<MoverItem[]>;
  /** Highest 24h range-vs-price — backed by /market/coins?sort_by=volatility. */
  volatility: Slice<MarketCoin[]>;

  fetchHeatmap: (options?: { silent?: boolean }) => Promise<void>;
  fetchVolume: (options?: { silent?: boolean }) => Promise<void>;
  fetchVolatility: (options?: { silent?: boolean }) => Promise<void>;
}

const empty = <T,>(data: T): Slice<T> => ({ data, loading: false, error: null });

export const useDashboardStore = create<DashboardState>((set, get) => {
  /**
   * One generic loader so the three slices share identical loading / error /
   * silent-refresh semantics: a background tick never flashes a skeleton or
   * replaces good data with an error, and concurrent identical requests are
   * coalesced (see utils/dedupe.ts).
   */
  async function load<K extends "heatmap" | "volume" | "volatility">(
    key: K,
    requestKey: string,
    request: () => Promise<DashboardState[K]["data"]>,
    errorFallback: string,
    silent: boolean
  ) {
    if (!silent) set({ [key]: { ...get()[key], loading: true, error: null } } as Partial<DashboardState>);
    try {
      const data = await dedupe(requestKey, request);
      set({ [key]: { data, loading: false, error: null } } as Partial<DashboardState>);
    } catch (error) {
      if (silent) return;
      set({
        [key]: { ...get()[key], loading: false, error: toErrorMessage(error, errorFallback) },
      } as Partial<DashboardState>);
    }
  }

  return {
    heatmap: empty<MarketCoin[]>([]),
    volume: empty<MoverItem[]>([]),
    volatility: empty<MarketCoin[]>([]),

    fetchHeatmap: (options) =>
      load(
        "heatmap",
        "dashboard-heatmap",
        async () =>
          (await fetchMarketCoins({ page: 1, limit: HEATMAP_SIZE, sortBy: "market_cap", sortDirection: "desc" })).items,
        "Market data could not be loaded. Please retry.",
        options?.silent ?? false
      ),

    fetchVolume: (options) =>
      load(
        "volume",
        "dashboard-volume",
        () => fetchTopByVolume(MOVERS_SIZE),
        "Market data could not be loaded. Please retry.",
        options?.silent ?? false
      ),

    fetchVolatility: (options) =>
      load(
        "volatility",
        "dashboard-volatility",
        async () =>
          (await fetchMarketCoins({ page: 1, limit: MOVERS_SIZE, sortBy: "volatility", sortDirection: "desc" })).items,
        "Market data could not be loaded. Please retry.",
        options?.silent ?? false
      ),
  };
});
