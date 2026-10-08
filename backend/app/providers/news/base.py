"""
Common news-provider interface.

A new source (another news API, a licensed feed) implements
`NewsProvider` and is registered in `app/providers/news/__init__.py`;
the ingestion service only ever talks to this interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.providers.news.models import NewsFetchResult


class NewsProvider(ABC):
    #: Short stable identifier stored in each article's `provider` field.
    provider_name: str

    @abstractmethod
    async def fetch_latest(
        self, *, before: Optional[datetime] = None, language: Optional[str] = None
    ) -> NewsFetchResult:
        """
        Return one page of the provider's newest articles, newest first.

        `before` pages backwards (only articles published before that
        instant). Raises a `ProviderError` subclass on timeout, rate
        limit, outage or an unusable response — never returns made-up data.
        """
        raise NotImplementedError
