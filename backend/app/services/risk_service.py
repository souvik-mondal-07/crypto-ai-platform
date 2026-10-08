"""Risk engine (Phase 14) — pure, deterministic, explainable.

    inputs -> 6 components (each 0-100, higher = riskier) -> weighted score -> level

Components (default weights, see app/config/risk_config.py):

    volatility 25%   ATR%, Bollinger width%, 24h range%
    liquidity  15%   24h volume, market cap, volume / market cap
    technical  20%   RSI, MACD, trend, Bollinger position, support/resistance
    fundamental 15%  fundamental score, market rank, mcap/FDV, supply, ATH drawdown, data completeness
    sentiment  10%   average score, negative share, trend, news volume
    prediction 15%   predicted direction, range width, model confidence

Each component is a weighted average of its AVAILABLE sub-factors; a component
with no available sub-factor is excluded and the remaining weights are
re-normalised. Missing data is never assumed to be low, neutral or zero risk —
it lowers `coverage`, and below `min_coverage` no risk score is produced.

No randomness, no clock, no I/O: the same inputs always give the same result.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from app.config.risk_config import (
    DEFAULT_ENGINE_CONFIG,
    RiskConfig,
)
from app.services.decision_inputs import DecisionInputs
from app.services.scoring import (
    fmt_money,
    level_for_rounded_score,
    piecewise,
    weighted_average,
)

COMPONENT_LABELS = {
    "volatility": "Volatility",
    "liquidity": "Liquidity",
    "technical": "Technical",
    "fundamental": "Fundamental",
    "sentiment": "Sentiment",
    "prediction": "ML prediction",
}


@dataclass
class RiskSubFactor:
    key: str
    label: str
    #: The raw input this sub-score was derived from (None for categorical inputs).
    value: Optional[float]
    score: float
    weight: float
    #: Sentence used when this sub-factor is a notable risk / notable strength.
    high_text: str
    low_text: str


@dataclass
class RiskComponent:
    key: str
    label: str
    weight: float
    available: bool
    score: Optional[float] = None
    #: Points this component adds to the final score (score * normalised weight).
    contribution: Optional[float] = None
    reason: Optional[str] = None
    factors: list[RiskSubFactor] = field(default_factory=list)


@dataclass
class RiskResult:
    available: bool
    score: Optional[float] = None
    level: Optional[str] = None
    #: Share (0-1) of the total component weight backed by real data.
    coverage: float = 0.0
    components: list[RiskComponent] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    reason: Optional[str] = None
    config_version: str = ""


# ---------------------------------------------------------------------------
# Sub-factor builders — each returns the list of sub-factors it can compute
# from REAL inputs (an empty list means "component unavailable").
# ---------------------------------------------------------------------------


def _sub(cfg: RiskConfig, component: str, key: str, label: str, value: Optional[float], score: float,
         high_text: str, low_text: str) -> RiskSubFactor:
    return RiskSubFactor(
        key=key, label=label, value=value, score=round(max(0.0, min(100.0, score)), 2),
        weight=cfg.sub_weights[component][key], high_text=high_text, low_text=low_text,
    )


def _volatility(inp: DecisionInputs, cfg: RiskConfig) -> list[RiskSubFactor]:
    out: list[RiskSubFactor] = []
    price = inp.market.price_usd if inp.market.status.usable else None
    t = inp.technical if inp.technical.status.usable else None

    if t is not None and price and t.atr is not None and t.atr >= 0:
        atr_pct = t.atr / price * 100
        out.append(_sub(cfg, "volatility", "atr_pct", "ATR % of price", atr_pct, piecewise(atr_pct, cfg.atr_pct_curve),
                        f"High volatility: ATR is {atr_pct:.1f}% of price per candle",
                        f"Low volatility: ATR is only {atr_pct:.1f}% of price per candle"))
    if t is not None and t.bollinger_upper is not None and t.bollinger_lower is not None and t.bollinger_middle:
        if t.bollinger_middle > 0 and t.bollinger_upper >= t.bollinger_lower:
            width = (t.bollinger_upper - t.bollinger_lower) / t.bollinger_middle * 100
            out.append(_sub(cfg, "volatility", "bollinger_width_pct", "Bollinger band width %", width,
                            piecewise(width, cfg.bollinger_width_curve),
                            f"Wide Bollinger Bands ({width:.1f}% of the middle band) indicate high historical volatility",
                            f"Narrow Bollinger Bands ({width:.1f}% of the middle band) indicate low historical volatility"))
    m = inp.market if inp.market.status.usable else None
    if m is not None and m.price_usd and m.high_24h_usd is not None and m.low_24h_usd is not None and m.high_24h_usd >= m.low_24h_usd:
        rng = (m.high_24h_usd - m.low_24h_usd) / m.price_usd * 100
        out.append(_sub(cfg, "volatility", "range_24h_pct", "24h price range %", rng, piecewise(rng, cfg.range_24h_curve),
                        f"Large 24h price swing ({rng:.1f}% between high and low)",
                        f"Small 24h price swing ({rng:.1f}% between high and low)"))
    return out


def _liquidity(inp: DecisionInputs, cfg: RiskConfig) -> list[RiskSubFactor]:
    m = inp.market
    if not m.status.usable:
        return []
    out: list[RiskSubFactor] = []
    if m.volume_24h_usd is not None and m.volume_24h_usd >= 0:
        v = m.volume_24h_usd
        out.append(_sub(cfg, "liquidity", "volume_24h_usd", "24h volume", v, piecewise(max(v, 1.0), cfg.volume_24h_curve),
                        f"Thin liquidity: 24h volume is only {fmt_money(v)}",
                        f"Strong liquidity: 24h volume is {fmt_money(v)}"))
    if m.market_cap_usd is not None and m.market_cap_usd > 0:
        c = m.market_cap_usd
        out.append(_sub(cfg, "liquidity", "market_cap_usd", "Market capitalisation", c, piecewise(c, cfg.market_cap_curve),
                        f"Small market capitalisation ({fmt_money(c)}) makes the price easier to move",
                        f"Large market capitalisation ({fmt_money(c)})"))
    if m.volume_24h_usd is not None and m.market_cap_usd is not None and m.market_cap_usd > 0 and m.volume_24h_usd >= 0:
        ratio = m.volume_24h_usd / m.market_cap_usd
        out.append(_sub(cfg, "liquidity", "volume_to_market_cap", "Volume / market cap", ratio,
                        piecewise(ratio, cfg.volume_to_mcap_curve),
                        f"Unhealthy trading turnover (24h volume is {ratio * 100:.1f}% of market cap)",
                        f"Healthy trading turnover (24h volume is {ratio * 100:.1f}% of market cap)"))
    return out


def _technical(inp: DecisionInputs, cfg: RiskConfig) -> list[RiskSubFactor]:
    t = inp.technical
    if not t.status.usable:
        return []
    out: list[RiskSubFactor] = []
    price = inp.market.price_usd if inp.market.status.usable else None

    if t.rsi is not None:
        r = t.rsi
        out.append(_sub(cfg, "technical", "rsi", "RSI", r, piecewise(r, cfg.rsi_risk_curve),
                        f"RSI ({r:.0f}) is at an extreme level, which raises the risk of a reversal",
                        f"RSI ({r:.0f}) is in a balanced range"))
    macd_key = None
    if t.macd_crossover in ("bullish_crossover", "bearish_crossover"):
        macd_key = t.macd_crossover
    elif t.macd_histogram is not None:
        macd_key = "hist_positive" if t.macd_histogram > 0 else "hist_negative"
    if macd_key is not None:
        out.append(_sub(cfg, "technical", "macd", "MACD", None, cfg.macd_risk[macd_key],
                        "MACD momentum is negative", "MACD momentum is positive"))
    if t.trend in cfg.trend_risk:
        out.append(_sub(cfg, "technical", "trend", "Trend", None, cfg.trend_risk[t.trend],
                        "The technical trend is bearish", "The technical trend is bullish"))
    if price and t.bollinger_upper is not None and t.bollinger_lower is not None and t.bollinger_upper > t.bollinger_lower:
        pb = (price - t.bollinger_lower) / (t.bollinger_upper - t.bollinger_lower)
        out.append(_sub(cfg, "technical", "bollinger_position", "Bollinger position", pb,
                        piecewise(pb, cfg.bollinger_position_risk_curve),
                        "Price is stretched near or beyond a Bollinger Band",
                        "Price is trading comfortably inside its Bollinger Bands"))
    sr = _support_resistance_share_down(price, t.support_levels, t.resistance_levels)
    if sr is not None:
        out.append(_sub(cfg, "technical", "support_resistance", "Support / resistance", sr,
                        piecewise(sr, cfg.sr_risk_curve),
                        "Price is close to resistance with limited upside room",
                        "Price is close to support, which limits the nearby downside"))
    return out


def support_resistance_share_down(price, supports, resistances):  # public alias used by the decision engine
    return _support_resistance_share_down(price, supports, resistances)


def _support_resistance_share_down(price: Optional[float], supports: list[float], resistances: list[float]) -> Optional[float]:
    """downside_to_support / (downside_to_support + upside_to_resistance); needs one level on each side."""
    if not price or price <= 0:
        return None
    below = [s for s in supports if s < price]
    above = [r for r in resistances if r > price]
    if not below or not above:
        return None
    down = (price - max(below)) / price
    up = (min(above) - price) / price
    total = down + up
    return down / total if total > 0 else None


def _fundamental(inp: DecisionInputs, cfg: RiskConfig) -> list[RiskSubFactor]:
    f = inp.fundamental
    if not f.status.usable:
        return []
    out: list[RiskSubFactor] = []
    if f.score is not None:
        out.append(_sub(cfg, "fundamental", "fundamental_score", "Fundamental score", f.score, 100.0 - f.score,
                        f"Weak fundamental score ({f.score:.0f}/100)", f"Strong fundamental score ({f.score:.0f}/100)"))
    if f.market_cap_rank is not None and f.market_cap_rank > 0:
        out.append(_sub(cfg, "fundamental", "market_rank", "Market rank", float(f.market_cap_rank),
                        piecewise(float(f.market_cap_rank), cfg.rank_risk_curve),
                        f"Low market rank (#{f.market_cap_rank})", f"Top market rank (#{f.market_cap_rank})"))
    if f.market_cap_to_fdv is not None and f.market_cap_to_fdv > 0:
        out.append(_sub(cfg, "fundamental", "market_cap_to_fdv", "Market cap / FDV", f.market_cap_to_fdv,
                        piecewise(f.market_cap_to_fdv, cfg.mcap_to_fdv_risk_curve),
                        f"Only {f.market_cap_to_fdv * 100:.0f}% of the fully diluted valuation is in circulation (dilution risk)",
                        f"{f.market_cap_to_fdv * 100:.0f}% of the fully diluted valuation is already in circulation"))
    if f.supply_type == "capped" and f.circulating_to_max_supply_percent is not None:
        p = f.circulating_to_max_supply_percent
        out.append(_sub(cfg, "fundamental", "supply", "Circulating / max supply", p,
                        piecewise(p, cfg.supply_circulating_risk_curve),
                        f"Only {p:.0f}% of the maximum supply is circulating (future dilution)",
                        f"{p:.0f}% of the maximum supply is already circulating"))
    if f.distance_from_ath_percent is not None and f.distance_from_ath_percent <= 0:
        d = abs(f.distance_from_ath_percent)
        out.append(_sub(cfg, "fundamental", "ath_drawdown", "Drawdown from all-time high", d,
                        piecewise(d, cfg.ath_drawdown_risk_curve),
                        f"Price is {d:.0f}% below its all-time high",
                        f"Price is only {d:.0f}% below its all-time high"))
    if f.coverage_percent is not None:
        c = f.coverage_percent
        out.append(_sub(cfg, "fundamental", "data_completeness", "Fundamental data completeness", c, 100.0 - c,
                        f"Fundamental data is incomplete ({c:.0f}% coverage)", f"Fundamental data is {c:.0f}% complete"))
    return out


def _sentiment(inp: DecisionInputs, cfg: RiskConfig) -> list[RiskSubFactor]:
    s = inp.sentiment
    if not s.status.usable or s.average_score is None:
        return []
    out = [_sub(cfg, "sentiment", "average_score", "Average sentiment score", s.average_score,
                piecewise(s.average_score, cfg.sentiment_score_risk_curve),
                "Recent news sentiment is negative", "Recent news sentiment is positive")]
    if s.negative_percent is not None:
        out.append(_sub(cfg, "sentiment", "negative_share", "Negative news share", s.negative_percent,
                        piecewise(s.negative_percent, cfg.sentiment_negative_pct_risk_curve),
                        f"{s.negative_percent:.0f}% of recent news is negative",
                        f"Only {s.negative_percent:.0f}% of recent news is negative"))
    if s.trend_direction in cfg.sentiment_trend_risk:
        out.append(_sub(cfg, "sentiment", "trend", "Sentiment trend", None, cfg.sentiment_trend_risk[s.trend_direction],
                        "Sentiment is declining compared with the previous period",
                        "Sentiment is improving compared with the previous period"))
    out.append(_sub(cfg, "sentiment", "news_volume", "News volume", float(s.total_articles),
                    piecewise(float(s.total_articles), cfg.news_volume_risk_curve),
                    f"Thin news coverage ({s.total_articles} analysed articles) makes sentiment less reliable",
                    f"Broad news coverage ({s.total_articles} analysed articles)"))
    return out


def _prediction(inp: DecisionInputs, cfg: RiskConfig) -> list[RiskSubFactor]:
    p = inp.prediction
    if not p.status.usable or p.direction not in cfg.prediction_direction_risk:
        return []
    out = [_sub(cfg, "prediction", "direction", "Predicted direction", None, cfg.prediction_direction_risk[p.direction],
                "The ML model predicts a decline", "The ML model predicts a rise")]
    if p.return_lower is not None and p.return_upper is not None and p.return_upper >= p.return_lower:
        w = p.return_upper - p.return_lower
        out.append(_sub(cfg, "prediction", "range_width", "Predicted return range width", w,
                        piecewise(w, cfg.prediction_range_width_curve),
                        f"The ML predicted return range is wide ({w * 100:.1f} percentage points)",
                        f"The ML predicted return range is narrow ({w * 100:.1f} percentage points)"))
    if p.confidence_status == "calibrated" and p.confidence is not None:
        out.append(_sub(cfg, "prediction", "model_confidence", "ML model confidence", p.confidence,
                        piecewise(p.confidence, cfg.prediction_confidence_risk_curve),
                        f"ML prediction confidence is low ({p.confidence * 100:.0f}%)",
                        f"ML prediction confidence is high ({p.confidence * 100:.0f}%)"))
    return out


_BUILDERS: dict[str, Callable[[DecisionInputs, RiskConfig], list[RiskSubFactor]]] = {
    "volatility": _volatility,
    "liquidity": _liquidity,
    "technical": _technical,
    "fundamental": _fundamental,
    "sentiment": _sentiment,
    "prediction": _prediction,
}

_UNAVAILABLE_REASON = {
    "volatility": "No usable volatility data (needs technical analysis and/or a 24h price range).",
    "liquidity": "No usable volume or market capitalisation data.",
    "technical": "Technical analysis is not available.",
    "fundamental": "Fundamental data is not available.",
    "sentiment": "Not enough analysed news to describe sentiment.",
    "prediction": "No usable ML prediction is available.",
}


def calculate_risk(inputs: DecisionInputs, cfg: RiskConfig = DEFAULT_ENGINE_CONFIG.risk) -> RiskResult:
    """Risk score (0-100), level and the components/factors behind them."""
    components: list[RiskComponent] = []
    for key, build in _BUILDERS.items():
        weight = float(cfg.component_weights.get(key, 0.0))
        factors = build(inputs, cfg)
        if not factors:
            components.append(RiskComponent(key=key, label=COMPONENT_LABELS[key], weight=weight, available=False,
                                            reason=_UNAVAILABLE_REASON[key]))
            continue
        score = weighted_average((f.score, f.weight) for f in factors)
        components.append(RiskComponent(key=key, label=COMPONENT_LABELS[key], weight=weight, available=True,
                                        score=round(score, 2) if score is not None else None, factors=factors))

    total_weight = sum(c.weight for c in components)
    avail = [c for c in components if c.available and c.score is not None]
    avail_weight = sum(c.weight for c in avail)
    coverage = (avail_weight / total_weight) if total_weight > 0 else 0.0
    result = RiskResult(available=False, coverage=round(coverage, 4), components=components,
                        config_version=DEFAULT_ENGINE_CONFIG.risk_config_version)

    if cfg.require_market and not inputs.market.status.usable:
        result.reason = inputs.market.status.reason or "Usable market data is required to establish a risk score."
        return result
    if not avail or avail_weight <= 0:
        result.reason = "No risk component has usable data."
        return result
    if not any(c.key in cfg.required_any_of for c in avail):
        result.reason = "Neither volatility nor liquidity data is available, so a risk score cannot be established."
        return result
    if coverage < cfg.min_coverage:
        result.reason = (f"Only {coverage * 100:.0f}% of the risk model is backed by data "
                         f"(at least {cfg.min_coverage * 100:.0f}% is required).")
        return result

    score = 0.0
    for c in avail:
        c.contribution = round((c.score or 0.0) * c.weight / avail_weight, 2)
        score += (c.score or 0.0) * c.weight / avail_weight
    score = round(max(0.0, min(100.0, score)), 1)
    result.available = True
    result.score = score
    result.level = level_for_rounded_score(score, cfg.level_bounds)
    result.positive_factors, result.negative_factors = _risk_factor_sentences(avail, cfg)
    return result


def risk_factor_items(components: list[RiskComponent], cfg: RiskConfig) -> tuple[list[tuple[float, str]], list[tuple[float, str]]]:
    """(positive, negative) risk factors as (strength 0-100, sentence), strongest first (ties by key)."""
    high: list[tuple[float, str, str]] = []
    low: list[tuple[float, str, str]] = []
    for c in components:
        for f in c.factors:
            if f.score >= cfg.high_risk_factor_at_or_above:
                high.append((f.score, f"{c.key}.{f.key}", f.high_text))
            elif f.score <= cfg.low_risk_factor_at_or_below:
                low.append((100.0 - f.score, f"{c.key}.{f.key}", f.low_text))
    key = lambda item: (-item[0], item[1])  # noqa: E731
    return [(s, t) for s, _, t in sorted(low, key=key)], [(s, t) for s, _, t in sorted(high, key=key)]


def _risk_factor_sentences(components: list[RiskComponent], cfg: RiskConfig) -> tuple[list[str], list[str]]:
    positive, negative = risk_factor_items(components, cfg)
    return [t for _, t in positive], [t for _, t in negative]


__all__ = ["RiskComponent", "RiskResult", "RiskSubFactor", "calculate_risk", "risk_factor_items", "support_resistance_share_down"]
