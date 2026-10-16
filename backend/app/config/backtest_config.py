"""Phase 17 limits. Bounded on purpose: backtests read real exchange candles, so every dimension is capped."""

MAX_COINS_PER_BACKTEST = 10            # never load the 21k-coin universe into a run
MAX_BACKTEST_DAYS = 365
MAX_BARS_PER_COIN = 5_000
MIN_BACKTEST_DAYS = 1
MAX_CAPITAL = 1_000_000_000.0
MAX_CONCURRENT_RUNS_PER_USER = 2
MAX_STORED_EQUITY_POINTS = 1_500
MAX_STORED_TRADES = 5_000
RUN_STALE_AFTER_SECONDS = 1_800        # a run still "running" after this is reported failed (process died)

#: outcome matching per refresh: bounded so one request/background task cannot run unbounded
REFRESH_MAX_RECORDS = 2_000
REFRESH_MAX_SCAN = 20_000
REFRESH_MIN_INTERVAL_SECONDS = 60
MAX_RESULTS_FOR_METRICS = 100_000
METRICS_CACHE_TTL_SECONDS = 60
CANDLE_CACHE_TTL_SECONDS = 300
CANDLE_CACHE_MAX_ENTRIES = 64
