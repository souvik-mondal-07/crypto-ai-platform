"""
Centralized collection-name registry.

Every collection name string lives here, exactly once. Application
code should always reference `CollectionName.X`, never a raw string
like `"coins"` — this keeps renames/typos to a single place and gives
autocomplete/type-checking on collection references.

MongoDB creates collections lazily on first write, so listing a name
here does NOT create the collection — it only reserves the name.
"""

from enum import Enum


class CollectionName(str, Enum):
    USERS = "users"
    COINS = "coins"
    MARKET_DATA = "market_data"
    HISTORICAL_PRICES = "historical_prices"
    TECHNICAL_ANALYSIS = "technical_analysis"
    FUNDAMENTAL_ANALYSIS = "fundamental_analysis"
    NEWS = "news"
    SENTIMENT = "sentiment"
    PREDICTIONS = "predictions"
    DECISIONS = "decisions"
    AI_ANALYSIS = "ai_analysis"
    PREDICTION_RESULTS = "prediction_results"
    WATCHLISTS = "watchlists"
    PORTFOLIOS = "portfolios"
    PORTFOLIO_TRANSACTIONS = "portfolio_transactions"
    ALERTS = "alerts"
    ANALYSIS_HISTORY = "analysis_history"
    MODEL_METRICS = "model_metrics"
