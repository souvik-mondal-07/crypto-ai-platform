from app.providers.news.base import NewsProvider
from app.providers.news.cryptocompare import CryptoCompareNewsProvider
from app.providers.news.models import NewsFetchResult, NormalizedNewsArticle


def get_news_providers() -> list[NewsProvider]:
    """
    The configured news providers. To add a source, implement
    `NewsProvider` and append it here — ingestion, deduplication and
    the API need no other change.
    """
    return [CryptoCompareNewsProvider()]


__all__ = [
    "NewsProvider",
    "CryptoCompareNewsProvider",
    "NewsFetchResult",
    "NormalizedNewsArticle",
    "get_news_providers",
]
