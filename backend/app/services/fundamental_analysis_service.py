"""
Fundamental analysis service (Phase 11) — orchestration.

    Provider -> FundamentalDataService -> FundamentalAnalysisService (this file)
             -> FundamentalAnalysisRepository -> FastAPI route

Resolves the coin, reads the live market snapshot from `market_data`,
obtains the (cached) provider project profile, runs the pure
calculations in fundamental_calculations.py, persists the calculation
snapshot, and shapes the response. Routes contain no logic of their own.

Market-derived metrics and the score are recalculated on EVERY request
from the current `market_data` snapshot (cheap arithmetic), so they can
never lag behind the market data the rest of the page shows. Only the
provider project profile is cached.
"""

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Optional, TypeVar

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.core.exceptions import AppError
from app.repositories.coin_repository import CoinRepository
from app.repositories.fundamental_analysis_repository import FundamentalAnalysisRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.converters import market_data_doc_to_schema
from app.schemas.fundamentals import (
    CalculatedMetrics,
    CommunityData,
    DevelopmentData,
    EcosystemData,
    FundamentalAnalysisResponse,
    FundamentalFreshness,
    FundamentalScore,
    FundamentalTimestamps,
    MarketOverview,
    PerformanceData,
    ProjectInfo,
    SummaryItem,
    SupplyData,
    ValuationData,
)
from app.services import fundamental_calculations as calc
from app.services.fundamental_data_service import FundamentalDataService, ProfileResult
from app.config.settings import get_settings

logger = logging.getLogger("crypto_ai_platform.services.fundamental_analysis")

DATA_SOURCE = "coingecko"

T = TypeVar("T")


async def _db(awaitable: Awaitable[T]) -> T:
    """Turn a MongoDB failure into a clean 503 instead of a generic 500."""
    try:
        return await awaitable
    except PyMongoError as exc:
        logger.error("Database error during fundamental analysis: %s", exc.__class__.__name__)
        raise AppError(
            503, "DATABASE_UNAVAILABLE", "The database is temporarily unavailable. Please try again shortly."
        ) from exc


def _development_input(dev_doc: dict[str, Any]) -> calc.DevelopmentInput:
    repos = dev_doc.get("repositories") or []
    return calc.DevelopmentInput(
        github_repo_count=len(repos),
        stars=dev_doc.get("stars"),
        forks=dev_doc.get("forks"),
        subscribers=dev_doc.get("subscribers"),
        total_issues=dev_doc.get("total_issues"),
        pull_request_contributors=dev_doc.get("pull_request_contributors"),
        commit_count_4_weeks=dev_doc.get("commit_count_4_weeks"),
    )


class FundamentalAnalysisService:
    def __init__(
        self,
        coin_repository: Optional[CoinRepository] = None,
        market_data_repository: Optional[MarketDataRepository] = None,
        repository: Optional[FundamentalAnalysisRepository] = None,
        data_service: Optional[FundamentalDataService] = None,
    ) -> None:
        self._coins = coin_repository or CoinRepository()
        self._market_data = market_data_repository or MarketDataRepository()
        self._repository = repository or FundamentalAnalysisRepository()
        self._data_service = data_service or FundamentalDataService(repository=self._repository)

    async def get_fundamentals(self, coin_id: str, force_refresh: bool = False) -> FundamentalAnalysisResponse:
        if not ObjectId.is_valid(coin_id):
            raise AppError(400, "INVALID_COIN_ID", "coin_id is not a valid identifier.")
        object_id = ObjectId(coin_id)

        coin_doc = await _db(self._coins.find_by_internal_id(coin_id))
        if coin_doc is None:
            raise AppError(404, "COIN_NOT_FOUND", f"No coin found with id '{coin_id}'.")

        market_doc = await _db(self._market_data.get_by_coin_id(object_id))
        cached = await _db(self._repository.get_by_coin_id(object_id))

        provider_coin_id = ((coin_doc.get("providers") or {}).get("coingecko") or {}).get("id")
        profile = await self._data_service.get_profile(
            object_id, coin_doc["symbol"], provider_coin_id, cached, force_refresh=force_refresh
        )

        if market_doc is None and profile.documents is None:
            if profile.error is not None:
                # Nothing to show and the provider is the reason: surface it
                # through the standard ProviderError handler (503/504/429).
                raise profile.error
            raise AppError(
                404, "FUNDAMENTALS_NOT_AVAILABLE",
                "No fundamental data is available for this coin yet: no market data has been "
                "synchronized and the provider has no project information for it.",
            )

        response, snapshot = self._build(coin_doc, market_doc, profile)

        try:
            await self._repository.save_analysis(object_id, coin_doc["symbol"], snapshot, response.timestamps.calculated_at)
        except PyMongoError as exc:
            # The calculation is valid and served; only its cache write failed.
            logger.warning("Could not persist fundamental analysis snapshot: %s", exc.__class__.__name__)
        return response

    # ------------------------------------------------------------------

    def _build(
        self, coin_doc: dict[str, Any], market_doc: Optional[dict[str, Any]], profile: ProfileResult
    ) -> tuple[FundamentalAnalysisResponse, dict[str, Any]]:
        calculated_at = datetime.now(timezone.utc)
        warnings: list[str] = []
        unavailable: list[str] = []

        md = market_data_doc_to_schema(market_doc) if market_doc is not None else None
        docs = profile.documents or {}
        project_doc = docs.get("project_info")
        ecosystem_doc = docs.get("ecosystem") or {}
        dev_doc = ecosystem_doc.get("development") or {}
        comm_doc = ecosystem_doc.get("community") or {}
        max_infinite = (docs.get("tokenomics") or {}).get("max_supply_infinite")

        rank = coin_doc.get("market_cap_rank")

        # ---- provider-reported market sections ---------------------------
        market = supply = valuation = None
        supply_type: calc.SupplyType = "not_reported"
        if md is not None:
            supply_type, supply_notes = calc.classify_supply(md.max_supply, max_infinite)
            market = MarketOverview(
                market_cap_usd=md.market_cap_usd, market_cap_rank=rank,
                volume_24h_usd=md.volume_24h_usd, fully_diluted_valuation_usd=md.fully_diluted_valuation_usd,
            )
            supply = SupplyData(
                circulating_supply=md.circulating_supply, total_supply=md.total_supply,
                max_supply=md.max_supply, supply_type=supply_type, notes=supply_notes,
            )
            valuation = ValuationData(
                current_price_usd=md.price_usd, ath_usd=md.ath_usd, atl_usd=md.atl_usd,
                ath_date=md.ath_date, atl_date=md.atl_date,
                ath_change_percentage=md.ath_change_percentage, atl_change_percentage=md.atl_change_percentage,
                performance=PerformanceData(
                    percent_change_1h=md.percent_change_1h, percent_change_24h=md.percent_change_24h,
                    percent_change_7d=md.percent_change_7d, percent_change_30d=md.percent_change_30d,
                    percent_change_1y=md.percent_change_1y,
                ),
            )
            if md.is_stale:
                warnings.append("Market data has not been refreshed recently and may be out of date.")
        else:
            unavailable.append("market")
            warnings.append("No market data has been synchronized for this coin yet.")

        # ---- provider-reported project / ecosystem -----------------------
        project_info = ecosystem = None
        dev_input = calc.DevelopmentInput()
        if project_doc is not None:
            project_doc = {k: v for k, v in project_doc.items() if v is not None}
            dev_doc = {k: v for k, v in dev_doc.items() if v is not None}
            comm_doc = {k: v for k, v in comm_doc.items() if v is not None}
            project_info = ProjectInfo(**project_doc)
            dev_input = _development_input(dev_doc)
            dev_available = calc.development_data_available(dev_input)
            ecosystem = EcosystemData(
                development=DevelopmentData(available=dev_available, **{
                    k: v for k, v in dev_doc.items() if k in DevelopmentData.model_fields and k != "available"
                }),
                community=CommunityData(**{k: v for k, v in comm_doc.items() if k in CommunityData.model_fields}),
            )
        else:
            unavailable.extend(["project_info", "ecosystem"])
            if profile.refresh_failed:
                warnings.append("Project information could not be retrieved from the provider right now.")
            else:
                warnings.append("The provider has no project information for this coin.")

        if project_doc is not None and profile.refresh_failed:
            warnings.append("Project information could not be refreshed; previously stored data is shown.")
        elif project_doc is not None and profile.is_stale:
            warnings.append("Project information is older than the refresh window and could not be updated; the last stored data is shown.")

        # ---- calculations -------------------------------------------------
        metrics = calc.compute_metrics(
            price_usd=md.price_usd if md else None,
            market_cap_usd=md.market_cap_usd if md else None,
            volume_24h_usd=md.volume_24h_usd if md else None,
            circulating_supply=md.circulating_supply if md else None,
            total_supply=md.total_supply if md else None,
            max_supply=md.max_supply if md else None,
            fully_diluted_valuation_usd=md.fully_diluted_valuation_usd if md else None,
            ath_usd=md.ath_usd if md else None,
            atl_usd=md.atl_usd if md else None,
        )
        for metric in (metrics.circulating_to_max_supply_percent, metrics.circulating_to_total_supply_percent,
                       metrics.market_cap_to_fdv):
            if metric.unavailable_reason and "inconsistent" in metric.unavailable_reason:
                warnings.append(metric.unavailable_reason)

        pi = project_info
        score_result = calc.compute_fundamental_score(
            calc.ScoreInputs(
                market_cap_usd=md.market_cap_usd if md else None,
                metrics=metrics,
                profile_present=pi is not None,
                has_description=bool(pi and pi.description),
                has_homepage=bool(pi and pi.homepage_urls),
                has_whitepaper=bool(pi and pi.whitepaper_url),
                has_explorer=bool(pi and pi.blockchain_explorer_urls),
                has_repository=dev_input.github_repo_count > 0,
                has_categories=bool(pi and pi.categories),
                genesis_date=pi.genesis_date if pi else None,
                development=dev_input,
            )
        )
        summary_items = calc.build_summary(
            market_cap_rank=rank,
            market_cap_usd=md.market_cap_usd if md else None,
            supply_type=supply_type,
            max_supply=md.max_supply if md else None,
            metrics=metrics,
            categories=pi.categories if pi else [],
            asset_platform_id=pi.asset_platform_id if pi else None,
            genesis_date=pi.genesis_date if pi else None,
            github_repo_count=dev_input.github_repo_count,
            development=dev_input,
            market_present=md is not None,
            profile_present=pi is not None,
        ) if md is not None or pi is not None else []

        market_updated_at = (market_doc.get("updated_at") or market_doc.get("last_updated")) if market_doc else None
        response = FundamentalAnalysisResponse(
            coin_id=str(coin_doc["_id"]),
            symbol=coin_doc["symbol"],
            name=coin_doc["name"],
            source=DATA_SOURCE,
            market_data_source=md.data_source if md else None,
            market=market, supply=supply, valuation=valuation,
            project_info=project_info, ecosystem=ecosystem,
            calculated_metrics=CalculatedMetrics.model_validate(asdict(metrics)),
            score=FundamentalScore.model_validate(asdict(score_result)),
            summary=[SummaryItem.model_validate(asdict(i)) for i in summary_items],
            timestamps=FundamentalTimestamps(
                fetched_at=profile.fetched_at, calculated_at=calculated_at,
                updated_at=calculated_at, market_data_updated_at=market_updated_at,
            ),
            freshness=FundamentalFreshness(
                market_data_is_stale=bool(md and md.is_stale),
                project_data_is_stale=profile.is_stale,
                project_refresh_failed=profile.refresh_failed,
            ),
            is_partial=bool(unavailable),
            unavailable_sections=unavailable,
            warnings=warnings,
        )

        dev_component = next((c for c in score_result.components if c.key == "development_activity"), None)
        snapshot = {
            "calculated": {
                "supply_type": supply_type,
                "metrics": {k: {"value": v["value"], "unit": v["unit"]} for k, v in asdict(metrics).items()},
                "score": asdict(score_result),
                "summary": [asdict(i) for i in summary_items],
            },
            "fundamental_score": score_result.score,
            "development_activity_score": dev_component.subscore if dev_component else None,
            "score_status": score_result.status,
            "score_method_version": score_result.method_version,
            "market_data_updated_at": market_updated_at,
            "market_data_source": md.data_source if md else None,
        }
        return response, snapshot
