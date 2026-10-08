"""Structured payload for the Gemini explanation (Phase 15) — pure functions, no I/O.

Every value here is COPIED from the existing engines' responses (market data, technical,
fundamental, news, sentiment, Phase 13 prediction, Phase 14 risk & decision). Nothing is computed,
estimated or defaulted: a section whose source is unavailable becomes

    {"available": false, "reason": "..."}

and is never turned into 0 / neutral / unknown / low risk. Only the fields that carry meaning for an
explanation are included (long histories and chart series are left out to keep the prompt small).
"""

import math
import re
from typing import Any, Optional

from app.ai.schemas.ai_analysis import AI_INPUT_MODULES, AIModuleAvailability
from app.schemas.decisions import DecisionResponse
from app.schemas.fundamentals import FundamentalAnalysisResponse
from app.schemas.market import MarketData
from app.schemas.news import NewsArticle
from app.schemas.predictions import PredictionResponse
from app.schemas.sentiment import CoinSentimentResponse
from app.schemas.technical_analysis import TechnicalAnalysisResponse

MAX_NEWS_ITEMS = 10
DESCRIPTION_EXCERPT_CHARS = 400


def unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _available(data: dict[str, Any]) -> dict[str, Any]:
    return {"available": True, **data}


def _clean(value: Any) -> Any:
    """Drop None values recursively (an absent field means "not reported", never a default)."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def coin_section(coin_id: str, symbol: Optional[str], name: Optional[str]) -> dict[str, Any]:
    return _clean({"id": coin_id, "symbol": symbol, "name": name})


def market_section(market: Optional[MarketData]) -> dict[str, Any]:
    if market is None:
        return unavailable("No market data has been synchronized for this coin.")
    return _available(_clean({
        "price_usd": market.price_usd,
        "market_cap_usd": market.market_cap_usd,
        "volume_24h_usd": market.volume_24h_usd,
        "high_24h_usd": market.high_24h_usd,
        "low_24h_usd": market.low_24h_usd,
        "percent_change_1h": market.percent_change_1h,
        "percent_change_24h": market.percent_change_24h,
        "percent_change_7d": market.percent_change_7d,
        "percent_change_30d": market.percent_change_30d,
        "percent_change_1y": market.percent_change_1y,
        "ath_usd": market.ath_usd,
        "atl_usd": market.atl_usd,
        "ath_change_percentage": market.ath_change_percentage,
        "last_updated": _iso(market.last_updated),
        "data_source": market.data_source,
        "is_stale": market.is_stale,
    }))


def technical_section(tech: Optional[TechnicalAnalysisResponse], reason: Optional[str] = None) -> dict[str, Any]:
    if tech is None:
        return unavailable(reason or "Technical analysis is unavailable.")
    return _available(_clean({
        "timeframe": tech.timeframe,
        "calculated_at": _iso(tech.calculated_at),
        "candle_count": tech.candle_count,
        "trend": tech.trend.trend,
        "rsi": {"period": tech.rsi.period, "current": tech.rsi.current, "zone": tech.rsi.zone},
        "macd": {
            "current": tech.macd.current.model_dump(exclude={"timestamp"}),
            "crossover": tech.macd.crossover,
        },
        "moving_averages": {"sma": tech.moving_averages.sma, "ema": tech.moving_averages.ema},
        "bollinger_bands": {
            "upper": tech.bollinger_bands.upper, "middle": tech.bollinger_bands.middle, "lower": tech.bollinger_bands.lower,
        },
        "atr": {"period": tech.atr.period, "current": tech.atr.current},
        "volume": {
            "current_volume_24h_usd": tech.volume.current_volume_24h_usd,
            "average_volume": tech.volume.average_volume,
            "volume_change_percent": tech.volume.volume_change_percent,
            "trend": tech.volume.trend,
        },
        "support_levels": tech.support_resistance.support_levels,
        "resistance_levels": tech.support_resistance.resistance_levels,
        "data_source": tech.data_source,
    }))


def fundamental_section(fund: Optional[FundamentalAnalysisResponse], reason: Optional[str] = None) -> dict[str, Any]:
    if fund is None:
        return unavailable(reason or "Fundamental analysis is unavailable.")
    metrics = fund.calculated_metrics
    calculated = {
        key: _clean({"value": m.value, "unit": m.unit, "unavailable_reason": m.unavailable_reason})
        for key, m in (
            ("volume_to_market_cap", metrics.volume_to_market_cap),
            ("market_cap_to_fdv", metrics.market_cap_to_fdv),
            ("circulating_to_max_supply_percent", metrics.circulating_to_max_supply_percent),
            ("circulating_to_total_supply_percent", metrics.circulating_to_total_supply_percent),
            ("distance_from_ath_percent", metrics.distance_from_ath_percent),
            ("distance_from_atl_percent", metrics.distance_from_atl_percent),
        )
    }
    project: dict[str, Any] = {}
    if fund.project_info is not None:
        description = (fund.project_info.description or "").strip()
        project = {
            "categories": fund.project_info.categories[:8],
            "hashing_algorithm": fund.project_info.hashing_algorithm,
            "block_time_in_minutes": fund.project_info.block_time_in_minutes,
            "genesis_date": fund.project_info.genesis_date,
            "description_excerpt": description[:DESCRIPTION_EXCERPT_CHARS] or None,
        }
    development: dict[str, Any] = {}
    if fund.ecosystem is not None:
        dev = fund.ecosystem.development
        development = {
            "available": dev.available,
            "commit_count_4_weeks": dev.commit_count_4_weeks,
            "stars": dev.stars, "forks": dev.forks,
        } if dev.available else {"available": False}
    return _available(_clean({
        "market": fund.market.model_dump() if fund.market else None,
        "supply": fund.supply.model_dump(exclude={"notes"}) if fund.supply else None,
        "valuation": fund.valuation.model_dump(mode="json") if fund.valuation else None,
        "calculated_metrics": calculated,
        "score": {
            "status": fund.score.status, "value": fund.score.score,
            "coverage_percent": fund.score.coverage_percent, "message": fund.score.message,
        },
        "summary": [item.text for item in fund.summary],
        "project": project or None,
        "development": development or None,
    }))


def news_section(articles: Optional[list[NewsArticle]], total: int = 0, reason: Optional[str] = None) -> dict[str, Any]:
    if articles is None:
        return unavailable(reason or "News is unavailable.")
    if not articles:
        return unavailable("No recent news articles are stored for this coin.")
    return _available({
        "total_related_articles": total,
        "recent_articles": [
            _clean({
                "title": a.title,
                "source": a.source,
                "published_at": _iso(a.published_at),
                "sentiment_label": a.sentiment.label if a.sentiment else None,
                "sentiment_score": round(a.sentiment.score, 3) if a.sentiment else None,
            })
            for a in articles[:MAX_NEWS_ITEMS]
        ],
    })


def sentiment_section(sent: Optional[CoinSentimentResponse], reason: Optional[str] = None) -> dict[str, Any]:
    if sent is None:
        return unavailable(reason or "Sentiment is unavailable.")
    if sent.status != "ok":
        return unavailable(
            f"Too few analysed news articles in the last {sent.timeframe} "
            f"({sent.total_articles} of the {sent.min_articles_required} required)."
        )
    return _available(_clean({
        "timeframe": sent.timeframe,
        "label": sent.sentiment_label,
        "average_score": sent.average_score,
        "total_articles": sent.total_articles,
        "positive_percent": sent.positive_percent,
        "neutral_percent": sent.neutral_percent,
        "negative_percent": sent.negative_percent,
        "trend": {"direction": sent.trend.direction, "change": sent.trend.change},
        "model_status": sent.model_status,
        "calculated_at": _iso(sent.calculated_at),
    }))


def prediction_section(pred: Optional[PredictionResponse], reason: Optional[str] = None) -> dict[str, Any]:
    if pred is None:
        return unavailable(reason or "Prediction engine unavailable")
    return _available(_clean({
        "kind": pred.kind,
        "horizon": pred.horizon,
        "direction": pred.direction,
        "predicted_return": pred.predicted_return,
        "predicted_return_range": pred.predicted_return_range.model_dump() if pred.predicted_return_range else None,
        "predicted_price_range": pred.predicted_price_range.model_dump() if pred.predicted_price_range else None,
        "range_nominal_coverage": pred.range_nominal_coverage,
        "reference_price_usd": pred.current_price,
        "confidence": pred.confidence,
        "confidence_status": pred.confidence_status,
        "confidence_note": pred.confidence_note,
        "model": pred.model,
        "model_version": pred.model_version,
        "generated_at": _iso(pred.generated_at),
        "is_stale": pred.is_stale,
    }))


def risk_section(decision: DecisionResponse) -> dict[str, Any]:
    risk = decision.risk
    if not risk.available or risk.score is None:
        return unavailable(risk.reason or "The risk score could not be established from the available data.")
    return _available(_clean({
        "score": risk.score,
        "level": risk.level,
        "coverage_percent": risk.coverage_percent,
        "components": [
            _clean({
                "key": c.key, "label": c.label, "weight": c.weight, "available": c.available,
                "score": c.score, "contribution": c.contribution, "reason": c.reason,
                "factors": [_clean({"label": f.label, "value": f.value, "score": f.score}) for f in c.factors],
            })
            for c in risk.components
        ],
        "positive_factors": risk.positive_factors,
        "negative_factors": risk.negative_factors,
        "config_version": risk.config_version,
    }))


def decision_section(decision: DecisionResponse) -> dict[str, Any]:
    """The OFFICIAL Phase 14 result, verbatim. Gemini explains it and must not change it."""
    if decision.decision is None:
        return {
            "available": False,
            "reason": decision.status_reason or "The decision engine could not produce a decision.",
            "status": decision.status,
            "signals": decision.signals.model_dump(),
            "data_quality": {k: getattr(decision.data_quality, k).model_dump(mode="json")
                             for k in ("market", "technical", "fundamental", "sentiment", "prediction")},
            "warnings": decision.warnings,
        }
    return _available(_clean({
        "decision": decision.decision,
        "status": decision.status,
        "decision_score": decision.decision_score,
        "raw_score": decision.raw_score,
        "risk_adjustment": decision.risk_adjustment,
        "confidence": decision.confidence,
        "confidence_status": decision.confidence_status,
        "risk_score": decision.risk_score,
        "risk_level": decision.risk_level,
        "signals": decision.signals.model_dump(),
        "signal_scores": decision.signal_scores.model_dump(),
        "module_weights": decision.module_weights,
        "positive_factors": decision.positive_factors,
        "negative_factors": decision.negative_factors,
        "base_decision": decision.base_decision,
        "overrides": [o.model_dump() for o in decision.overrides],
        "agreement": decision.agreement.model_dump(),
        "data_quality": {k: getattr(decision.data_quality, k).model_dump(mode="json")
                         for k in ("market", "technical", "fundamental", "sentiment", "prediction")},
        "warnings": decision.warnings,
        "engine_explanation": decision.explanation,
        "engine_version": decision.engine_version,
    }))


def build_payload(
    *,
    coin: dict[str, Any],
    market: dict[str, Any],
    technical: dict[str, Any],
    fundamental: dict[str, Any],
    news: dict[str, Any],
    sentiment: dict[str, Any],
    prediction: dict[str, Any],
    risk: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "coin": coin, "market": market, "technical": technical, "fundamental": fundamental, "news": news,
        "sentiment": sentiment, "prediction": prediction, "risk": risk, "decision": decision,
    }


# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------


def availability_of(payload: dict[str, Any]) -> dict[str, AIModuleAvailability]:
    """Which inputs the explanation was built from (and why any are missing)."""
    out: dict[str, AIModuleAvailability] = {}
    for module in AI_INPUT_MODULES:
        section = payload.get(module) or {}
        out[module] = AIModuleAvailability(available=bool(section.get("available", False)), reason=section.get("reason"))
    return out


def insufficient_reason(payload: dict[str, Any]) -> Optional[str]:
    """Why an explanation cannot be written honestly at all (None when there is enough to explain).

    Needs the market snapshot AND at least one analysis module; with less, Gemini would only have
    "everything is unavailable" to talk about.
    """
    avail = availability_of(payload)
    analysis = ("technical", "fundamental", "news", "sentiment", "prediction")
    if not avail["market"].available or not any(avail[m].available for m in analysis):
        missing = ", ".join(m for m in ("market", *analysis) if not avail[m].available)
        return f"Not enough platform data to explain this coin yet. Unavailable: {missing}."
    return None


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def collect_numbers(payload: Any) -> list[float]:
    """Every numeric value in the payload (including numbers inside strings), for the invented-price check."""
    found: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            if math.isfinite(node):
                found.append(float(node))
        elif isinstance(node, str):
            for m in _NUMBER_RE.findall(node.replace(",", "")):
                try:
                    found.append(float(m))
                except ValueError:
                    pass
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(payload)
    return found
