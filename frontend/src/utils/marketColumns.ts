import type { MarketCoin, MarketCoinSortField } from "../types/market";

/**
 * Column catalogue for the Markets table. Only fields the backend's
 * GET /market/coins actually returns are listed. `sortField` is set only for
 * columns the backend can sort server-side; the rest are display-only.
 * "Rank" and "Coin" are structural (always shown) and live in the table.
 */
export type ColumnKey =
  | "price"
  | "change_24h"
  | "change_7d"
  | "market_cap"
  | "volume"
  | "fdv"
  | "supply"
  | "volatility"
  | "ath"
  | "atl"
  | "status";

export interface ColumnDef {
  key: ColumnKey;
  label: string;
  /** Short tooltip explaining the metric. */
  help?: string;
  sortField?: MarketCoinSortField;
  defaultVisible: boolean;
}

export const COLUMNS: ColumnDef[] = [
  { key: "price", label: "Price", sortField: "price", defaultVisible: true },
  { key: "change_24h", label: "24H", sortField: "change_24h", defaultVisible: true },
  { key: "change_7d", label: "7D", sortField: "change_7d", defaultVisible: true },
  { key: "market_cap", label: "Market Cap", sortField: "market_cap", defaultVisible: true },
  { key: "volume", label: "24H Volume", sortField: "volume", defaultVisible: true },
  { key: "fdv", label: "FDV", sortField: "fdv", help: "Fully diluted valuation: price × maximum supply", defaultVisible: true },
  { key: "supply", label: "Circulating Supply", sortField: "supply", defaultVisible: true },
  { key: "volatility", label: "24H Range", sortField: "volatility", help: "(24H high − low) ÷ price", defaultVisible: false },
  { key: "ath", label: "ATH", help: "All-time high price", defaultVisible: false },
  { key: "atl", label: "ATL", help: "All-time low price", defaultVisible: false },
  { key: "status", label: "Data", help: "Freshness of this coin's market snapshot", defaultVisible: true },
];

export const DEFAULT_VISIBLE: ColumnKey[] = COLUMNS.filter((column) => column.defaultVisible).map((column) => column.key);

/** Drops unknown keys (e.g. from an older saved layout) so a stale value can't break the table. */
export function sanitizeVisible(value: unknown): ColumnKey[] {
  if (!Array.isArray(value)) return DEFAULT_VISIBLE;
  const known = new Set<string>(COLUMNS.map((column) => column.key));
  const kept = value.filter((item): item is ColumnKey => typeof item === "string" && known.has(item));
  return kept.length > 0 ? kept : DEFAULT_VISIBLE;
}

export function isoOrNull(coin: MarketCoin): string | null {
  return coin.last_updated;
}
