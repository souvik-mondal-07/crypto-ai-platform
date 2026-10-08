"""
Service-level tests for FundamentalDataService + FundamentalAnalysisService,
using in-memory fakes — no MongoDB, no live network.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.core.exceptions import AppError
from app.providers.errors import ProviderNotFoundError, ProviderUnavailableError
from app.providers.normalized import (
    NormalizedCoinProfile,
    NormalizedCommunityData,
    NormalizedDeveloperData,
)
from app.services.fundamental_analysis_service import FundamentalAnalysisService
from app.services.fundamental_data_service import FundamentalDataService, profile_to_documents

NOW = datetime.now(timezone.utc)
FORBIDDEN = re.compile(r"\b(buy|sell|hold|guarantee[ds]?|profit|recommend\w*)\b", re.IGNORECASE)


def _coin_doc(**overrides):
    doc = {
        "_id": ObjectId(), "name": "Examplecoin", "symbol": "EXC", "slug": "examplecoin",
        "logo_url": None, "market_cap_rank": 12, "is_active": True,
        "providers": {"coingecko": {"id": "examplecoin", "available": True}},
        "created_at": NOW, "updated_at": NOW,
    }
    doc.update(overrides)
    return doc


def _market_doc(coin_id, **overrides):
    doc = {
        "coin_id": coin_id, "price_usd": 50.0, "market_cap_usd": 1_000_000_000.0,
        "volume_24h_usd": 50_000_000.0, "circulating_supply": 15_000_000.0,
        "total_supply": 18_000_000.0, "max_supply": 21_000_000.0,
        "fully_diluted_valuation_usd": 1_400_000_000.0, "ath_usd": 200.0, "atl_usd": 10.0,
        "ath_change_percentage": -74.9, "atl_change_percentage": 399.0,
        "percent_change_24h": 1.5, "percent_change_1y": 30.0,
        "data_source": "coingecko", "updated_at": NOW, "last_updated": NOW,
    }
    doc.update(overrides)
    return doc


def _profile(**overrides):
    profile = NormalizedCoinProfile(
        coingecko_id="examplecoin", description="A test asset.",
        homepage_urls=["https://example.org"], whitepaper_url="https://example.org/wp.pdf",
        blockchain_explorer_urls=["https://explorer.example.org"], categories=["Layer 1 (L1)"],
        github_repos=["https://github.com/example/core"], genesis_date="2015-01-01",
        max_supply_infinite=False,
        developer=NormalizedDeveloperData(stars=100, forks=20, commit_count_4_weeks=60),
        community=NormalizedCommunityData(reddit_subscribers=1000),
    )
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


class FakeCoinRepository:
    def __init__(self, docs=None, error=None):
        self.docs, self.error = docs if docs is not None else [], error

    async def find_by_internal_id(self, internal_id):
        if self.error:
            raise self.error
        return next((d for d in self.docs if str(d["_id"]) == internal_id), None)


class FakeMarketDataRepository:
    def __init__(self, doc=None):
        self.doc = doc

    async def get_by_coin_id(self, coin_id):
        return self.doc


class FakeFundamentalRepository:
    def __init__(self, cached=None, save_error=None):
        self.cached, self.save_error = cached, save_error
        self.profile_saves, self.analysis_saves = [], []

    async def get_by_coin_id(self, coin_id):
        return self.cached

    async def save_profile(self, coin_id, symbol, payload, fetched_at):
        if self.save_error:
            raise self.save_error
        self.profile_saves.append((coin_id, symbol, payload, fetched_at))

    async def save_analysis(self, coin_id, symbol, payload, calculated_at):
        if self.save_error:
            raise self.save_error
        self.analysis_saves.append((coin_id, symbol, payload, calculated_at))

    @staticmethod
    def age_seconds(fetched_at):
        from app.repositories.fundamental_analysis_repository import FundamentalAnalysisRepository
        return FundamentalAnalysisRepository.age_seconds(fetched_at)


class FakeProvider:
    supports_coin_profile = True

    def __init__(self, profile=None, error=None):
        self.profile, self.error, self.calls = profile, error, 0

    async def get_coin_profile(self, provider_coin_id):
        self.calls += 1
        if self.error:
            raise self.error
        return self.profile


def _cached_doc(profile, fetched_at):
    return {**profile_to_documents(profile), "fetched_at": fetched_at}


def _service(coin, market=None, repo=None, provider=None, coins_error=None):
    repo = repo or FakeFundamentalRepository()
    provider = provider or FakeProvider(_profile())
    service = FundamentalAnalysisService(
        coin_repository=FakeCoinRepository([coin] if coin else [], error=coins_error),
        market_data_repository=FakeMarketDataRepository(market),
        repository=repo,
        data_service=FundamentalDataService(repository=repo, provider=provider),
    )
    return service, repo, provider


# ---- validation / lookup ----------------------------------------------------


async def test_invalid_coin_id_is_400():
    service, _, _ = _service(None)
    with pytest.raises(AppError) as exc:
        await service.get_fundamentals("not-an-object-id")
    assert exc.value.status_code == 400 and exc.value.code == "INVALID_COIN_ID"


async def test_unknown_coin_is_404():
    service, _, provider = _service(None)
    with pytest.raises(AppError) as exc:
        await service.get_fundamentals(str(ObjectId()))
    assert exc.value.status_code == 404 and exc.value.code == "COIN_NOT_FOUND"
    assert provider.calls == 0


async def test_database_failure_on_lookup_is_503_not_500():
    coin = _coin_doc()
    service, _, _ = _service(coin, coins_error=PyMongoError("boom"))
    with pytest.raises(AppError) as exc:
        await service.get_fundamentals(str(coin["_id"]))
    assert exc.value.status_code == 503 and exc.value.code == "DATABASE_UNAVAILABLE"


# ---- happy path -------------------------------------------------------------


async def test_full_response_combines_market_profile_and_calculations():
    coin = _coin_doc()
    service, repo, provider = _service(coin, _market_doc(coin["_id"]))
    result = await service.get_fundamentals(str(coin["_id"]))

    assert result.symbol == "EXC" and result.source == "coingecko"
    assert result.market.market_cap_usd == 1_000_000_000.0 and result.market.market_cap_rank == 12
    assert result.supply.supply_type == "capped"
    assert result.valuation.ath_usd == 200.0 and result.valuation.performance.percent_change_1y == 30.0
    assert result.project_info.categories == ["Layer 1 (L1)"]
    assert result.ecosystem.development.available is True
    assert result.ecosystem.development.commit_count_4_weeks == 60

    metrics = result.calculated_metrics
    assert metrics.origin == "calculated"
    assert metrics.volume_to_market_cap.value == pytest.approx(0.05)
    assert metrics.distance_from_ath_percent.value == pytest.approx(-75.0)
    assert metrics.circulating_to_max_supply_percent.value == pytest.approx(15 / 21 * 100)

    assert result.score.status == "scored" and result.score.coverage_percent == 100.0
    assert 0 <= result.score.score <= 100
    assert result.is_partial is False and result.unavailable_sections == []
    assert result.warnings == []
    assert provider.calls == 1


async def test_provider_reported_and_calculated_ath_values_are_kept_separate():
    coin = _coin_doc()
    service, _, _ = _service(coin, _market_doc(coin["_id"], ath_change_percentage=-74.9))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.valuation.ath_change_percentage == -74.9  # provider-reported, untouched
    assert result.calculated_metrics.distance_from_ath_percent.value == pytest.approx(-75.0)  # calculated


async def test_snapshot_is_persisted_without_copying_market_data():
    coin = _coin_doc()
    service, repo, _ = _service(coin, _market_doc(coin["_id"]))
    result = await service.get_fundamentals(str(coin["_id"]))

    assert len(repo.profile_saves) == 1 and len(repo.analysis_saves) == 1
    _, symbol, payload, calculated_at = repo.analysis_saves[0]
    assert symbol == "EXC" and calculated_at == result.timestamps.calculated_at
    assert payload["fundamental_score"] == result.score.score
    assert payload["score_method_version"] == result.score.method_version
    for market_field in ("price_usd", "market_cap_usd", "circulating_supply", "ath_usd"):
        assert market_field not in payload
        assert market_field not in repo.profile_saves[0][2]


async def test_timestamps_are_populated():
    coin = _coin_doc()
    service, _, _ = _service(coin, _market_doc(coin["_id"]))
    ts = (await service.get_fundamentals(str(coin["_id"]))).timestamps
    assert ts.fetched_at is not None and ts.calculated_at is not None
    assert ts.updated_at is not None and ts.market_data_updated_at is not None


async def test_summary_is_factual_and_free_of_advice():
    coin = _coin_doc()
    service, _, _ = _service(coin, _market_doc(coin["_id"]))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.summary
    for item in result.summary:
        assert not FORBIDDEN.search(item.text), item.text


# ---- caching / refresh policy ----------------------------------------------


async def test_fresh_cached_profile_does_not_call_the_provider():
    coin = _coin_doc()
    cached = _cached_doc(_profile(), NOW - timedelta(minutes=5))
    service, repo, provider = _service(coin, _market_doc(coin["_id"]), FakeFundamentalRepository(cached))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert provider.calls == 0 and repo.profile_saves == []
    assert result.project_info is not None
    assert result.timestamps.fetched_at == cached["fetched_at"]


async def test_expired_cached_profile_is_refetched():
    coin = _coin_doc()
    cached = _cached_doc(_profile(description="old"), NOW - timedelta(hours=7))
    service, _, provider = _service(coin, _market_doc(coin["_id"]), FakeFundamentalRepository(cached))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert provider.calls == 1
    assert result.project_info.description == "A test asset."


async def test_force_refresh_respects_the_minimum_interval():
    coin = _coin_doc()
    cached = _cached_doc(_profile(), NOW - timedelta(seconds=10))
    service, _, provider = _service(coin, _market_doc(coin["_id"]), FakeFundamentalRepository(cached))
    await service.get_fundamentals(str(coin["_id"]), force_refresh=True)
    assert provider.calls == 0


async def test_force_refresh_refetches_once_the_interval_has_passed():
    coin = _coin_doc()
    cached = _cached_doc(_profile(description="old"), NOW - timedelta(minutes=10))
    service, _, provider = _service(coin, _market_doc(coin["_id"]), FakeFundamentalRepository(cached))
    result = await service.get_fundamentals(str(coin["_id"]), force_refresh=True)
    assert provider.calls == 1 and result.project_info.description == "A test asset."


async def test_market_metrics_are_recalculated_even_when_profile_is_cached():
    coin = _coin_doc()
    cached = _cached_doc(_profile(), NOW - timedelta(minutes=5))
    market = _market_doc(coin["_id"], price_usd=100.0)
    service, _, _ = _service(coin, market, FakeFundamentalRepository(cached))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.calculated_metrics.distance_from_ath_percent.value == pytest.approx(-50.0)


# ---- partial data / failures -----------------------------------------------


async def test_provider_failure_without_cache_returns_partial_market_data():
    coin = _coin_doc()
    provider = FakeProvider(error=ProviderUnavailableError("down"))
    service, _, _ = _service(coin, _market_doc(coin["_id"]), provider=provider)
    result = await service.get_fundamentals(str(coin["_id"]))

    assert result.market is not None and result.supply is not None
    assert result.project_info is None and result.ecosystem is None
    assert result.is_partial is True
    assert set(result.unavailable_sections) == {"project_info", "ecosystem"}
    assert result.freshness.project_refresh_failed is True
    assert result.timestamps.fetched_at is None
    assert any("could not be retrieved" in w for w in result.warnings)
    # Score still built from real data only: coverage < 100, never invented.
    assert result.score.coverage_percent == 65.0  # size 25 + liquidity 20 + supply 20
    assert result.score.status == "scored"
    assert not next(c for c in result.score.components if c.key == "information_completeness").available


async def test_provider_failure_with_stored_profile_serves_it_flagged_stale():
    coin = _coin_doc()
    cached = _cached_doc(_profile(description="stored copy"), NOW - timedelta(hours=9))
    provider = FakeProvider(error=ProviderUnavailableError("down"))
    service, _, _ = _service(coin, _market_doc(coin["_id"]), FakeFundamentalRepository(cached), provider)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.project_info.description == "stored copy"
    assert result.freshness.project_data_is_stale is True
    assert result.freshness.project_refresh_failed is True
    assert result.timestamps.fetched_at == cached["fetched_at"]  # not presented as fresh
    assert result.is_partial is False


async def test_provider_404_with_old_stored_profile_warns_that_it_is_stale():
    coin = _coin_doc()
    cached = _cached_doc(_profile(description="stored copy"), NOW - timedelta(hours=9))
    provider = FakeProvider(error=ProviderNotFoundError("404"))
    service, _, _ = _service(coin, _market_doc(coin["_id"]), FakeFundamentalRepository(cached), provider)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.project_info.description == "stored copy"
    assert result.freshness.project_data_is_stale is True
    assert result.freshness.project_refresh_failed is False
    assert any("older than the refresh window" in w for w in result.warnings)


async def test_provider_failure_with_nothing_else_available_propagates_the_provider_error():
    coin = _coin_doc()
    provider = FakeProvider(error=ProviderUnavailableError("down"))
    service, _, _ = _service(coin, market=None, provider=provider)
    with pytest.raises(ProviderUnavailableError):
        await service.get_fundamentals(str(coin["_id"]))


async def test_no_market_data_and_no_provider_profile_is_404():
    coin = _coin_doc()
    provider = FakeProvider(error=ProviderNotFoundError("404"))
    service, _, _ = _service(coin, market=None, provider=provider)
    with pytest.raises(AppError) as exc:
        await service.get_fundamentals(str(coin["_id"]))
    assert exc.value.status_code == 404 and exc.value.code == "FUNDAMENTALS_NOT_AVAILABLE"


async def test_provider_404_with_market_data_is_partial_not_an_error():
    coin = _coin_doc()
    provider = FakeProvider(error=ProviderNotFoundError("404"))
    service, _, _ = _service(coin, _market_doc(coin["_id"]), provider=provider)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.project_info is None and result.freshness.project_refresh_failed is False
    assert any("no project information" in w for w in result.warnings)


async def test_profile_only_when_market_data_is_missing():
    coin = _coin_doc()
    service, _, _ = _service(coin, market=None)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.market is None and result.supply is None and result.valuation is None
    assert result.unavailable_sections == ["market"]
    assert result.project_info is not None
    assert all(m.value is None and m.unavailable_reason for m in vars(result.calculated_metrics).values()
               if hasattr(m, "unavailable_reason"))
    assert result.score.status == "not_enough_data" and result.score.score is None
    assert result.score.message == "Not enough data"
    text = " ".join(i.text for i in result.summary)
    assert "supply" not in text.lower()  # a data gap is not stated as a fact


async def test_coin_without_provider_mapping_skips_the_provider():
    coin = _coin_doc(providers={"binance": {"symbol": "EXCUSDT", "available": True}})
    service, _, provider = _service(coin, _market_doc(coin["_id"]))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert provider.calls == 0 and result.project_info is None and result.market is not None


async def test_persisting_the_analysis_failing_does_not_fail_the_request():
    coin = _coin_doc()
    repo = FakeFundamentalRepository(save_error=PyMongoError("write failed"))
    service, _, _ = _service(coin, _market_doc(coin["_id"]), repo)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.score.status == "scored" and result.project_info is not None


# ---- supply edge cases ------------------------------------------------------


async def test_missing_max_supply_is_not_reported_and_never_assumed_unlimited():
    coin = _coin_doc()
    market = _market_doc(coin["_id"], max_supply=None)
    provider = FakeProvider(_profile(max_supply_infinite=None))
    service, _, _ = _service(coin, market, provider=provider)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.supply.supply_type == "not_reported"
    assert result.calculated_metrics.circulating_to_max_supply_percent.value is None
    assert result.calculated_metrics.circulating_to_max_supply_percent.unavailable_reason
    assert result.calculated_metrics.circulating_to_total_supply_percent.value is not None


async def test_explicit_infinite_flag_gives_unlimited():
    coin = _coin_doc()
    market = _market_doc(coin["_id"], max_supply=None)
    service, _, _ = _service(coin, market, provider=FakeProvider(_profile(max_supply_infinite=True)))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.supply.supply_type == "unlimited"
    assert any("unlimited supply" in i.text for i in result.summary)


async def test_inconsistent_supply_data_is_flagged_not_clamped():
    coin = _coin_doc()
    market = _market_doc(coin["_id"], circulating_supply=30_000_000.0)
    service, _, _ = _service(coin, market)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.calculated_metrics.circulating_to_max_supply_percent.value is None
    assert any("inconsistent" in w for w in result.warnings)


async def test_all_zero_developer_block_is_reported_unavailable():
    coin = _coin_doc()
    profile = _profile(developer=NormalizedDeveloperData(stars=0, forks=0, commit_count_4_weeks=0))
    service, _, _ = _service(coin, _market_doc(coin["_id"]), provider=FakeProvider(profile))
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.ecosystem.development.available is False
    assert not next(c for c in result.score.components if c.key == "development_activity").available


# ---- freshness --------------------------------------------------------------


async def test_stale_market_data_is_flagged_and_warned():
    coin = _coin_doc()
    old = NOW - timedelta(hours=10)
    market = _market_doc(coin["_id"], updated_at=old, last_updated=old)
    service, _, _ = _service(coin, market)
    result = await service.get_fundamentals(str(coin["_id"]))
    assert result.freshness.market_data_is_stale is True
    assert any("may be out of date" in w for w in result.warnings)
    assert result.timestamps.market_data_updated_at == old
