/** Types for the Phase 16 user features. They mirror backend/app/schemas/{watchlist,portfolio,history,alerts,profile}.py. */

export interface Page {
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// ---- watchlist ------------------------------------------------------------
export interface WatchlistItem {
  coin_id: string;
  name: string;
  symbol: string;
  logo_url: string | null;
  market_cap_rank: number | null;
  price_usd: number | null;
  percent_change_24h: number | null;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  last_updated: string | null;
  is_stale: boolean;
  added_at: string;
}
export interface WatchlistResponse extends Page {
  items: WatchlistItem[];
}
export interface WatchlistStatus {
  coin_id: string;
  in_watchlist: boolean;
}

// ---- portfolio ------------------------------------------------------------
export interface Holding {
  coin_id: string;
  name: string;
  symbol: string;
  logo_url: string | null;
  quantity: number;
  average_buy_price: number;
  invested_value: number;
  has_price: boolean;
  current_price: number | null;
  current_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  percent_change_24h: number | null;
  allocation_pct: number | null;
  price_last_updated: string | null;
  price_is_stale: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
export interface PortfolioSummary {
  total_current_value: number;
  total_invested: number;
  priced_invested: number;
  total_unrealized_pnl: number | null;
  total_unrealized_pnl_pct: number | null;
  holdings_count: number;
  unpriced_count: number;
  is_partial: boolean;
}
export interface Portfolio {
  summary: PortfolioSummary;
  holdings: Holding[];
  currency: "USD";
}
export interface HoldingCreate {
  coin_id: string;
  quantity: number;
  price: number;
  fee?: number;
  bought_at?: string;
  notes?: string;
}
export interface HoldingUpdate {
  quantity?: number;
  average_buy_price?: number;
  notes?: string | null;
}
export interface PortfolioTransaction {
  id: string;
  coin_id: string;
  name: string | null;
  symbol: string | null;
  transaction_type: "buy" | "adjustment";
  quantity: number;
  price: number;
  fee: number | null;
  notes: string | null;
  transaction_at: string;
  created_at: string;
}
export interface TransactionList extends Page {
  items: PortfolioTransaction[];
}

// ---- history --------------------------------------------------------------
export type AnalysisType = "coin_analysis" | "prediction" | "risk_decision" | "ai_analysis";
export interface HistoryEntry {
  id: string;
  coin_id: string;
  coin_name: string | null;
  symbol: string | null;
  analysis_type: AnalysisType;
  status: "COMPLETED" | "UNAVAILABLE";
  decision: string | null;
  risk_level: string | null;
  risk_score: number | null;
  summary: string | null;
  created_at: string;
}
export interface HistoryList extends Page {
  items: HistoryEntry[];
}

// ---- alerts ---------------------------------------------------------------
export type AlertCondition = "ABOVE" | "BELOW";
export type AlertStatus = "ACTIVE" | "TRIGGERED" | "DISABLED" | "EXPIRED";
export interface PriceAlert {
  id: string;
  coin_id: string;
  name: string | null;
  symbol: string | null;
  logo_url: string | null;
  alert_type: "price";
  condition: AlertCondition;
  target_price: number;
  status: AlertStatus;
  current_price: number | null;
  created_at: string;
  updated_at: string;
  triggered_at: string | null;
  triggered_price: number | null;
  expires_at: string | null;
  last_checked_at: string | null;
}
export interface AlertList extends Page {
  items: PriceAlert[];
}
export interface AlertCreate {
  coin_id: string;
  condition: AlertCondition;
  target_price: number;
  expires_at?: string;
}
export interface AlertUpdate {
  condition?: AlertCondition;
  target_price?: number;
  status?: "ACTIVE" | "DISABLED";
  expires_at?: string | null;
}
export interface AlertCheckResult {
  checked: number;
  triggered: number;
  expired: number;
  skipped_no_price: number;
  skipped_stale: number;
  triggered_alert_ids: string[];
  checked_at: string;
}

// ---- profile / settings ----------------------------------------------------
export interface Profile {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at: string;
}
export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_new_password: string;
}
export type ThemePreference = "light" | "dark";
export interface UserSettings {
  theme: ThemePreference | null;
  notifications: { price_alerts: boolean };
}
export interface UserSettingsUpdate {
  theme?: ThemePreference | null;
  notifications?: { price_alerts?: boolean };
}
