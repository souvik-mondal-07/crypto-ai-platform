"""
Coin association for news articles (Phase 12).

Relevance comes from structured signals — never from a frontend string
search:

  1. Provider tags. CryptoCompare tags an article with the tickers it is
     about (e.g. categories "BTC|ETH|Exchange"). Coin tickers arrive
     ALL-CAPS while topic words ("Exchange", "Mining") are Title Case, and
     a stop-list removes the all-caps topic labels (ICO, NFT, ...).
  2. Explicit cashtags in the headline ("$SOL jumps ...").

Free-text coin-name matching in headlines is intentionally NOT done:
names like "Cosmos" or "Polygon" are ordinary words and would create
false associations.

A ticker is not unique across 21k coins, so each ticker resolves to the
highest-ranked ACTIVE coin (lowest market_cap_rank) with that symbol;
tickers that only match unranked coins are not associated. This is a
heuristic, documented as such — articles it cannot place stay global-only.
"""

import re
from typing import Iterable, Optional

from bson import ObjectId

from app.providers.news.models import NormalizedNewsArticle
from app.repositories.coin_repository import CoinRepository

_TICKER_RE = re.compile(r"^[A-Z0-9]{2,10}$")
_CASHTAG_RE = re.compile(r"(?<![A-Za-z0-9])\$([A-Za-z][A-Za-z0-9]{1,9})(?![A-Za-z0-9])")

#: All-caps provider labels that are topics, not coin tickers.
NON_TICKER_LABELS = frozenset(
    {
        "ICO", "IEO", "IDO", "NFT", "NFTS", "DEFI", "DAO", "ETF", "ETFS", "AI", "FIAT", "OTHER",
        "ALTCOIN", "BLOCKCHAIN", "MARKET", "TRADING", "BUSINESS", "MINING", "WALLET", "EXCHANGE",
        "REGULATION", "TECHNOLOGY", "SPONSORED", "ASIA", "COMMODITY", "CRYPTOCURRENCY", "GENERAL",
        "STABLECOIN", "STABLECOINS", "CBDC", "SEC", "USD", "EUR", "GBP", "JPY", "KRW", "CNY",
        "WEB3", "METAVERSE", "GAMING", "SECURITY", "SCAM", "HACK", "PODCAST", "VIDEO", "OPINION",
    }
)


def extract_candidate_symbols(article: NormalizedNewsArticle) -> list[str]:
    """Ordered, de-duplicated candidate tickers for one article (pure function)."""
    found: list[str] = []

    def add(symbol: str) -> None:
        if symbol not in found:
            found.append(symbol)

    for label in article.categories:
        if label.isupper() and _TICKER_RE.match(label) and label not in NON_TICKER_LABELS:
            add(label)
    for match in _CASHTAG_RE.finditer(article.title):
        symbol = match.group(1).upper()
        if _TICKER_RE.match(symbol) and symbol not in NON_TICKER_LABELS:
            add(symbol)
    return found


class NewsCoinMatcher:
    def __init__(self, coin_repository: Optional[CoinRepository] = None) -> None:
        self._coins = coin_repository or CoinRepository()

    async def resolve_symbols(self, symbols: Iterable[str]) -> dict[str, ObjectId]:
        """ticker -> internal coin ObjectId, for tickers that map to a ranked active coin."""
        unique = sorted(set(symbols))
        if not unique:
            return {}
        best = await self._coins.find_best_by_symbols(unique)
        return {symbol: doc["_id"] for symbol, doc in best.items()}

    @staticmethod
    def associate(
        candidates: list[str], resolved: dict[str, ObjectId]
    ) -> tuple[list[ObjectId], list[str]]:
        """Keep candidates that resolved to a coin, preserving order. Returns (coin ids, symbols)."""
        ids: list[ObjectId] = []
        symbols: list[str] = []
        for symbol in candidates:
            coin_id = resolved.get(symbol)
            if coin_id is not None and coin_id not in ids:
                ids.append(coin_id)
                symbols.append(symbol)
        return ids, symbols
