"""
Fundamental data service (Phase 11) — obtains the provider-reported
project / ecosystem profile for a coin, with a caching and failure policy.

    CoinGecko /coins/{id}  (via the provider abstraction)
            v
    FundamentalDataService (this file)  -> normalized profile documents
            v
    FundamentalAnalysisRepository       -> `fundamental_analysis`

Market figures (market cap, supply, ATH/ATL) are NOT fetched here; they
already live in `market_data`. Only slow-changing project information
is cached, so opening a Coin Details page is normally a pure database
read, and the provider is asked at most once per TTL per coin.

Failure policy (no fabricated data on any path):
  - provider 404      -> "no profile available", not treated as a failure
  - provider error    -> serve the previously stored profile if there is
                         one (flagged stale/refresh-failed), else none
  - persistence error -> logged; the freshly fetched data is still used
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.config.settings import get_settings
from app.providers.coingecko import CoinGeckoProvider
from app.providers.errors import ProviderError, ProviderNotFoundError
from app.providers.normalized import NormalizedCoinProfile
from app.repositories.fundamental_analysis_repository import FundamentalAnalysisRepository

logger = logging.getLogger("crypto_ai_platform.services.fundamental_data")


@dataclass
class ProfileResult:
    #: Stored-shape documents: {"project_info", "ecosystem", "tokenomics"} or None.
    documents: Optional[dict[str, Any]]
    fetched_at: Optional[datetime]
    #: A provider refresh was attempted and failed.
    refresh_failed: bool = False
    #: Stored data older than the TTL is being served (refresh failed / unavailable).
    is_stale: bool = False
    #: The provider error, kept so the caller can surface it if nothing else is available.
    error: Optional[ProviderError] = None


def profile_to_documents(profile: NormalizedCoinProfile) -> dict[str, Any]:
    """Normalized profile -> the storage/response document shape."""
    dev = profile.developer
    comm = profile.community
    return {
        "project_info": {
            "description": profile.description,
            "homepage_urls": profile.homepage_urls,
            "whitepaper_url": profile.whitepaper_url,
            "blockchain_explorer_urls": profile.blockchain_explorer_urls,
            "categories": profile.categories,
            "asset_platform_id": profile.asset_platform_id,
            "contract_addresses": profile.contract_addresses,
            "hashing_algorithm": profile.hashing_algorithm,
            "block_time_in_minutes": profile.block_time_in_minutes,
            "genesis_date": profile.genesis_date,
        },
        "ecosystem": {
            "development": {
                "repositories": profile.github_repos,
                "forks": dev.forks,
                "stars": dev.stars,
                "subscribers": dev.subscribers,
                "total_issues": dev.total_issues,
                "closed_issues": dev.closed_issues,
                "pull_requests_merged": dev.pull_requests_merged,
                "pull_request_contributors": dev.pull_request_contributors,
                "commit_count_4_weeks": dev.commit_count_4_weeks,
                "code_additions_4_weeks": dev.code_additions_4_weeks,
                "code_deletions_4_weeks": dev.code_deletions_4_weeks,
            },
            "community": {
                "official_forum_urls": profile.official_forum_urls,
                "announcement_urls": profile.announcement_urls,
                "chat_urls": profile.chat_urls,
                "twitter_screen_name": profile.twitter_screen_name,
                "subreddit_url": profile.subreddit_url,
                "telegram_channel_identifier": profile.telegram_channel_identifier,
                "reddit_subscribers": comm.reddit_subscribers,
                "telegram_channel_user_count": comm.telegram_channel_user_count,
            },
        },
        "tokenomics": {"max_supply_infinite": profile.max_supply_infinite},
    }


def _stored_documents(cached: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not cached or cached.get("project_info") is None:
        return None
    return {
        "project_info": cached.get("project_info"),
        "ecosystem": cached.get("ecosystem"),
        "tokenomics": cached.get("tokenomics") or {},
    }


class FundamentalDataService:
    def __init__(
        self,
        repository: Optional[FundamentalAnalysisRepository] = None,
        provider: Optional[CoinGeckoProvider] = None,
    ) -> None:
        self._repository = repository or FundamentalAnalysisRepository()
        self._provider = provider or CoinGeckoProvider()

    async def get_profile(
        self,
        coin_object_id: ObjectId,
        symbol: str,
        provider_coin_id: Optional[str],
        cached: Optional[dict[str, Any]],
        force_refresh: bool = False,
    ) -> ProfileResult:
        settings = get_settings()
        stored = _stored_documents(cached)
        stored_fetched_at = cached.get("fetched_at") if stored else None
        age = FundamentalAnalysisRepository.age_seconds(stored_fetched_at)

        ttl = settings.FUNDAMENTALS_PROFILE_TTL_SECONDS
        min_interval = settings.FUNDAMENTALS_MIN_REFRESH_INTERVAL_SECONDS
        if age is None:
            needs_refresh = True
        elif age > ttl:
            needs_refresh = True
        else:
            # Fresh enough — only an explicit refresh past the floor re-fetches.
            needs_refresh = force_refresh and age > min_interval

        if not needs_refresh:
            return ProfileResult(documents=stored, fetched_at=stored_fetched_at)

        def fallback(*, failed: bool, error: Optional[ProviderError] = None) -> ProfileResult:
            return ProfileResult(
                documents=stored,
                fetched_at=stored_fetched_at,
                refresh_failed=failed,
                is_stale=bool(stored) and age is not None and age > ttl,
                error=error,
            )

        if not provider_coin_id or not self._provider.supports_coin_profile:
            return fallback(failed=False)

        try:
            profile = await self._provider.get_coin_profile(provider_coin_id)
        except ProviderNotFoundError:
            logger.info("Provider has no profile for coin %s", provider_coin_id)
            return fallback(failed=False)
        except ProviderError as exc:
            logger.warning("Profile refresh failed for %s: %s", provider_coin_id, exc.__class__.__name__)
            return fallback(failed=True, error=exc)

        if profile is None:
            return fallback(failed=False)

        documents = profile_to_documents(profile)
        fetched_at = datetime.now(timezone.utc)
        try:
            await self._repository.save_profile(coin_object_id, symbol, documents, fetched_at)
        except PyMongoError as exc:
            # The fetched data is real and usable even if it couldn't be cached.
            logger.warning("Could not persist fundamental profile: %s", exc.__class__.__name__)
        return ProfileResult(documents=documents, fetched_at=fetched_at)
