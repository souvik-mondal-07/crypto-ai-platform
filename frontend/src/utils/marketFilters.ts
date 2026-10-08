import type { MarketCoinFilter, MarketCoinFilters, MarketCoinSortField } from "../types/market";

/**
 * Single source of truth for the Markets page's category tabs and range
 * presets. Dashboard "Quick Discovery" links build their URLs from the same
 * keys, so a link can never point at a tab or preset that doesn't exist.
 *
 * Every preset maps onto a filter the backend GET /market/coins actually
 * supports (market cap, volume, 24h change, max-supply) — nothing here is
 * filtered client-side.
 */

// ---------------------------------------------------------------- tabs ----

export type MarketTabKey = "all" | "gainers" | "losers" | "trending" | "volume" | "volatility" | "watchlist";

export interface MarketTab {
  key: MarketTabKey;
  label: string;
  /** The server-side view this tab applies (ignored for trending/watchlist, which use an id set). */
  filter: MarketCoinFilter;
  sortBy: MarketCoinSortField;
  sortDirection: "asc" | "desc";
}

export const MARKET_TABS: MarketTab[] = [
  { key: "all", label: "All Coins", filter: "all", sortBy: "market_cap", sortDirection: "desc" },
  { key: "gainers", label: "Gainers", filter: "gainers", sortBy: "change_24h", sortDirection: "desc" },
  { key: "losers", label: "Losers", filter: "losers", sortBy: "change_24h", sortDirection: "asc" },
  { key: "trending", label: "Trending", filter: "all", sortBy: "market_cap", sortDirection: "desc" },
  { key: "volume", label: "Highest Volume", filter: "all", sortBy: "volume", sortDirection: "desc" },
  { key: "volatility", label: "Highest Volatility", filter: "all", sortBy: "volatility", sortDirection: "desc" },
  { key: "watchlist", label: "Watchlist", filter: "all", sortBy: "market_cap", sortDirection: "desc" },
];

export function isMarketTabKey(value: string | null | undefined): value is MarketTabKey {
  return MARKET_TABS.some((tab) => tab.key === value);
}

// ------------------------------------------------------------- presets ----

interface Range {
  min?: number;
  max?: number;
}

export interface Preset<K extends string> extends Range {
  key: K;
  label: string;
}

const B = 1_000_000_000;
const M = 1_000_000;

export type CapKey = "any" | "gt100b" | "gt10b" | "10b-100b" | "1b-10b" | "lt1b";
export const CAP_PRESETS: Preset<CapKey>[] = [
  { key: "any", label: "Any" },
  { key: "gt100b", label: "> $100B", min: 100 * B },
  { key: "gt10b", label: "> $10B (large cap)", min: 10 * B },
  { key: "10b-100b", label: "$10B – $100B", min: 10 * B, max: 100 * B },
  { key: "1b-10b", label: "$1B – $10B", min: 1 * B, max: 10 * B },
  { key: "lt1b", label: "< $1B (small cap)", max: 1 * B },
];

export type ChangeKey = "any" | "gt10" | "5to10" | "0to5" | "0toN5" | "N5toN10" | "ltN10";
export const CHANGE_PRESETS: Preset<ChangeKey>[] = [
  { key: "any", label: "Any" },
  { key: "gt10", label: "> +10%", min: 10 },
  { key: "5to10", label: "+5% to +10%", min: 5, max: 10 },
  { key: "0to5", label: "0% to +5%", min: 0, max: 5 },
  { key: "0toN5", label: "0% to −5%", min: -5, max: 0 },
  { key: "N5toN10", label: "−5% to −10%", min: -10, max: -5 },
  { key: "ltN10", label: "< −10%", max: -10 },
];

export type VolumeKey = "any" | "gt1b" | "100m-1b" | "10m-100m" | "lt10m";
export const VOLUME_PRESETS: Preset<VolumeKey>[] = [
  { key: "any", label: "Any" },
  { key: "gt1b", label: "> $1B", min: 1 * B },
  { key: "100m-1b", label: "$100M – $1B", min: 100 * M, max: 1 * B },
  { key: "10m-100m", label: "$10M – $100M", min: 10 * M, max: 100 * M },
  { key: "lt10m", label: "< $10M", max: 10 * M },
];

export type SupplyKey = "any" | "capped" | "uncapped";
export const SUPPLY_OPTIONS: { key: SupplyKey; label: string }[] = [
  { key: "any", label: "Any" },
  { key: "capped", label: "Has maximum supply" },
  { key: "uncapped", label: "No reported maximum supply" },
];

export interface FilterSelection {
  cap: CapKey;
  change: ChangeKey;
  volume: VolumeKey;
  supply: SupplyKey;
}

export const DEFAULT_SELECTION: FilterSelection = { cap: "any", change: "any", volume: "any", supply: "any" };

function find<K extends string>(presets: Preset<K>[], key: K): Range {
  return presets.find((preset) => preset.key === key) ?? {};
}

/** Translate the UI selection into the exact query bounds the backend takes. */
export function selectionToFilters(selection: FilterSelection): MarketCoinFilters {
  const cap = find(CAP_PRESETS, selection.cap);
  const change = find(CHANGE_PRESETS, selection.change);
  const volume = find(VOLUME_PRESETS, selection.volume);

  const filters: MarketCoinFilters = {};
  if (cap.min !== undefined) filters.marketCapMin = cap.min;
  if (cap.max !== undefined) filters.marketCapMax = cap.max;
  if (change.min !== undefined) filters.changeMin = change.min;
  if (change.max !== undefined) filters.changeMax = change.max;
  if (volume.min !== undefined) filters.volumeMin = volume.min;
  if (volume.max !== undefined) filters.volumeMax = volume.max;
  if (selection.supply === "capped") filters.hasMaxSupply = true;
  if (selection.supply === "uncapped") filters.hasMaxSupply = false;
  return filters;
}

export function activeFilterCount(selection: FilterSelection): number {
  return (Object.keys(selection) as (keyof FilterSelection)[]).filter(
    (key) => selection[key] !== DEFAULT_SELECTION[key]
  ).length;
}

/** Reads a preset key from a URL value, falling back to "any" for anything unknown. */
export function parseCap(value: string | null): CapKey {
  return CAP_PRESETS.some((preset) => preset.key === value) ? (value as CapKey) : "any";
}
