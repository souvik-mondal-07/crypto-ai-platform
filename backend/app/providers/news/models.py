"""
Provider-neutral news article model (Phase 12).

Every news provider maps its own response shape into
`NormalizedNewsArticle`, so ingestion, deduplication and storage never
depend on which provider an article came from.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class NormalizedNewsArticle:
    provider: str
    #: The provider's own stable identifier, when it supplies one.
    provider_article_id: Optional[str]
    title: str
    #: Original article URL at the publisher (never a fabricated link).
    url: str
    #: Publisher name as reported by the provider (e.g. "CoinDesk").
    source: str
    #: Timezone-aware UTC.
    published_at: datetime
    description: Optional[str] = None
    image_url: Optional[str] = None
    author: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    language: Optional[str] = None


@dataclass
class NewsFetchResult:
    """One provider page: valid articles plus a count of entries that were dropped as malformed."""

    articles: list[NormalizedNewsArticle]
    malformed_count: int = 0
    #: Oldest `published_at` on the page — the cursor for fetching the next (older) page.
    oldest_published_at: Optional[datetime] = None
