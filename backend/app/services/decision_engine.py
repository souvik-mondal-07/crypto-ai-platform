"""Decision engine (Phase 14) — pure, deterministic, explainable. no LLM, no randomness.

    technical  ─┐
    fundamental ─┼─> weighted module scores (-100..+100) ─> raw score
    sentiment  ─┤                                             │
    prediction ─┘                       risk score (risk_service) ─> risk adjustment ─> final score
                                                                                         │
                                  thresholds + documented override rules ────────────────┘
                                                                                         ▼
                                                                          BUY / HOLD / SELL (or null + status)

Everything numeric lives in app/config/risk_config.py. Overrides are applied in
this order and every one that fires is returned in `overrides`:

    1. risk_buy_gate         BUY at HIGH / VERY_HIGH risk needs a stronger score, else HOLD
    2. signal_conflict       BUY/SELL while the modules clearly disagree and the score is weak -> HOLD
    3. low_confidence        BUY/SELL with decision confidence below the minimum -> HOLD
    4. risk_sell_escalation  HOLD with a mildly negative score at HIGH / VERY_HIGH risk -> SELL
                             (only when 1-3 did not fire)

When the inputs cannot support an honest decision, `decision` is None and
`status` explains why (INSUFFICIENT_DATA / STALE_DATA / PREDICTION_UNAVAILABLE /
ANALYSIS_UNAVAILABLE) — a decision is never forced.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.config.risk_config import (
    DECISION_BUY,
    DECISION_HOLD,
    DECISION_SELL,
    DEFAULT_ENGINE_CONFIG,
    MODULES,
    STATE_INSUFFICIENT,
    STATE_STALE,
    STATE_UNAVAILABLE,
    STATUS_ANALYSIS_UNAVAILABLE,
    STATUS_INSUFFICIENT_DATA,
    STATUS_PREDICTION_UNAVAILABLE,
    STATUS_STALE_DATA,
    STATUS_VALID,
    DecisionConfig,
    EngineConfig,
)
from app.services.decision_inputs import DecisionInputs
from app.services.risk_service import RiskResult, calculate_risk, risk_factor_items, support_resistance_share_down
from app.services.scoring import clamp, piecewise, sign, weighted_average

MAX_FACTORS_PER_SIDE = 8

SIGNAL_UNAVAILABLE = "UNAVAILABLE"
_LABELS = {
    "technical": ("BULLISH", "NEUTRAL", "BEARISH"),
    "fundamental": ("STRONG", "NEUTRAL", "WEAK"),
    "sentiment": ("POSITIVE", "NEUTRAL", "NEGATIVE"),
    "prediction": ("BULLISH", "NEUTRAL", "BEARISH"),
}


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ComponentScore:
    key: str
    score: float  # -100..+100
    weight: float
    positive_text: Optional[str] = None
    negative_text: Optional[str] = None


@dataclass
class ModuleSignal:
    key: str
    usable: bool
    score: Optional[float] = None  # -100..+100
    label: str = SIGNAL_UNAVAILABLE
    #: Share of the module's base weight that is applied (sentiment reliability; 1.0 otherwise).
    reliability: float = 1.0
    reason: Optional[str] = None
    components: list[ComponentScore] = field(default_factory=list)
    #: Extra sentences that are not tied to a single component (e.g. prediction caveats).
    extra_positive: list[str] = field(default_factory=list)
    extra_negative: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: Weighted share of the module's signed components that agree with the module's direction (0-1).
    intra_agreement: Optional[float] = None


@dataclass
class DecisionResult:
    status: str
    status_reason: Optional[str]
    decision: Optional[str]
    decision_score: Optional[float]
    raw_score: Optional[float]
    risk_adjustment: Optional[float]
    confidence: Optional[float]
    confidence_status: str  # "computed" | "unavailable"
    base_decision: Optional[str]
    risk: RiskResult
    signals: dict[str, str]
    signal_scores: dict[str, Optional[float]]
    effective_weights: dict[str, float]
    positive_factors: list[str]
    negative_factors: list[str]
    overrides: list[dict[str, str]]
    agreement: dict[str, Any]
    data_quality: dict[str, Any]
    warnings: list[str]
    explanation: list[str]
    engine_version: str
    risk_config_version: str


# ---------------------------------------------------------------------------
# Module signals
# ---------------------------------------------------------------------------


def _finish_module(key: str, comps: list[ComponentScore], cfg: DecisionConfig, reason_if_empty: str) -> ModuleSignal:
    if not comps:
        return ModuleSignal(key=key, usable=False, reason=reason_if_empty)
    score = weighted_average((c.score, c.weight) for c in comps)
    assert score is not None
    score = round(clamp(score, -100.0, 100.0), 2)
    # Agreement between the module's own signed components.
    pos_w = sum(c.weight for c in comps if sign(c.score, cfg.agreement_sign_threshold) > 0)
    neg_w = sum(c.weight for c in comps if sign(c.score, cfg.agreement_sign_threshold) < 0)
    intra = (max(pos_w, neg_w) / (pos_w + neg_w)) if (pos_w + neg_w) > 0 else None
    return ModuleSignal(key=key, usable=True, score=score, label=_label(key, score, cfg), components=comps, intra_agreement=intra)


def _label(key: str, score: float, cfg: DecisionConfig) -> str:
    up, mid, down = _LABELS[key]
    threshold = cfg.fundamental_label_threshold if key == "fundamental" else cfg.signal_label_threshold
    if score >= threshold:
        return up
    if score <= -threshold:
        return down
    return mid


def technical_signal(inp: DecisionInputs, cfg: DecisionConfig) -> ModuleSignal:
    t = inp.technical
    if not t.status.usable:
        return ModuleSignal(key="technical", usable=False, reason=t.status.reason or "Technical analysis is not available.")
    w = cfg.technical_weights
    price = inp.market.price_usd if inp.market.status.usable else None
    comps: list[ComponentScore] = []

    if t.trend in cfg.trend_score:
        comps.append(ComponentScore("trend", cfg.trend_score[t.trend], w["trend"],
                                    "The technical trend is bullish", "The technical trend is bearish"))

    macd_key = None
    if t.macd_crossover in ("bullish_crossover", "bearish_crossover"):
        macd_key = t.macd_crossover
    elif t.macd_histogram is not None:
        macd_key = "hist_positive" if t.macd_histogram > 0 else "hist_negative"
    if macd_key is not None:
        comps.append(ComponentScore("macd", cfg.macd_score[macd_key], w["macd"],
                                    "Positive MACD momentum", "Negative MACD momentum"))

    if t.rsi is not None:
        r = t.rsi
        comps.append(ComponentScore(
            "rsi", piecewise(r, cfg.rsi_score_curve), w["rsi"],
            f"RSI ({r:.0f}) shows healthy bullish momentum",
            f"RSI ({r:.0f}) is overbought" if r >= 70 else f"RSI ({r:.0f}) shows weak momentum",
        ))

    if price:
        refs = [(f"SMA {k}", v) for k, v in sorted(t.sma.items(), key=lambda kv: int(kv[0])) if v]
        refs += [(f"EMA {k}", v) for k, v in sorted(t.ema.items(), key=lambda kv: int(kv[0])) if v]
        if refs:
            above = sum(1 for _, v in refs if price > v)
            below = sum(1 for _, v in refs if price < v)
            score = (above - below) / len(refs) * cfg.moving_average_step
            comps.append(ComponentScore("moving_averages", score, w["moving_averages"],
                                        f"Price is above {above} of {len(refs)} key moving averages",
                                        f"Price is below {below} of {len(refs)} key moving averages"))

    if price and t.bollinger_upper is not None and t.bollinger_lower is not None and t.bollinger_upper > t.bollinger_lower:
        pb = (price - t.bollinger_lower) / (t.bollinger_upper - t.bollinger_lower)
        comps.append(ComponentScore("bollinger", piecewise(pb, cfg.bollinger_score_curve), w["bollinger"],
                                    "Price is near the lower Bollinger Band (possible rebound zone)",
                                    "Price is stretched above the upper Bollinger Band"))

    share_down = support_resistance_share_down(price, t.support_levels, t.resistance_levels)
    if share_down is not None:
        comps.append(ComponentScore("support_resistance", piecewise(share_down, cfg.support_resistance_score_curve),
                                    w["support_resistance"],
                                    "Price is close to support, which limits the nearby downside",
                                    "Price is close to resistance"))
    return _finish_module("technical", comps, cfg, "Technical analysis has no usable indicators.")


def fundamental_signal(inp: DecisionInputs, cfg: DecisionConfig) -> ModuleSignal:
    f = inp.fundamental
    if not f.status.usable:
        return ModuleSignal(key="fundamental", usable=False, reason=f.status.reason or "Fundamental data is not available.")
    w = cfg.fundamental_weights
    comps: list[ComponentScore] = []
    if f.score is not None:
        comps.append(ComponentScore("fundamental_score", clamp((f.score - 50.0) * 2.0, -100.0, 100.0), w["fundamental_score"],
                                    f"Strong fundamental score ({f.score:.0f}/100)", f"Weak fundamental score ({f.score:.0f}/100)"))
    if f.market_cap_rank is not None and f.market_cap_rank > 0:
        rank = f.market_cap_rank
        comps.append(ComponentScore("market_rank", piecewise(float(rank), cfg.rank_score_curve), w["market_rank"],
                                    f"Strong market position (rank #{rank})", f"Weak market position (rank #{rank})"))
    if f.market_cap_to_fdv is not None and f.market_cap_to_fdv > 0:
        r = f.market_cap_to_fdv
        comps.append(ComponentScore("market_cap_to_fdv", piecewise(r, cfg.mcap_to_fdv_score_curve), w["market_cap_to_fdv"],
                                    f"{r * 100:.0f}% of the fully diluted valuation is already in circulation",
                                    f"Only {r * 100:.0f}% of the fully diluted valuation is in circulation (dilution risk)"))
    return _finish_module("fundamental", comps, cfg, "Fundamental data has no usable metrics.")


def sentiment_signal(inp: DecisionInputs, cfg: DecisionConfig) -> ModuleSignal:
    s = inp.sentiment
    if not s.status.usable or s.average_score is None:
        return ModuleSignal(key="sentiment", usable=False,
                            reason=s.status.reason or "Not enough analysed news to describe sentiment.")
    w = cfg.sentiment_weights
    comps = [ComponentScore("average_score", clamp(s.average_score * 100.0, -100.0, 100.0), w["average_score"],
                            "Positive recent news sentiment", "Negative recent news sentiment")]
    if s.positive_percent is not None and s.negative_percent is not None:
        comps.append(ComponentScore("label_balance", clamp(s.positive_percent - s.negative_percent, -100.0, 100.0),
                                    w["label_balance"],
                                    f"{s.positive_percent:.0f}% of recent news is positive vs {s.negative_percent:.0f}% negative",
                                    f"{s.negative_percent:.0f}% of recent news is negative vs {s.positive_percent:.0f}% positive"))
    if s.trend_direction in cfg.sentiment_trend_score:
        comps.append(ComponentScore("trend", cfg.sentiment_trend_score[s.trend_direction], w["trend"],
                                    "Sentiment is improving compared with the previous period",
                                    "Sentiment is declining compared with the previous period"))
    module = _finish_module("sentiment", comps, cfg, "No sentiment components.")
    module.reliability = clamp(s.total_articles / float(cfg.sentiment_full_reliability_articles), 0.0, 1.0)
    if module.reliability < 1.0:
        module.notes.append(
            f"Sentiment is based on {s.total_articles} analysed articles (full weight needs "
            f"{cfg.sentiment_full_reliability_articles}), so it counts at {module.reliability * 100:.0f}% weight."
        )
    return module


def prediction_signal(inp: DecisionInputs, cfg: DecisionConfig) -> ModuleSignal:
    p = inp.prediction
    if not p.status.usable or p.direction is None or p.predicted_return is None:
        return ModuleSignal(key="prediction", usable=False, reason=p.status.reason or "No usable ML prediction is available.")
    horizon = p.horizon or "the"
    r = p.predicted_return
    base = piecewise(r, cfg.prediction_return_score_curve)
    consistent = (p.direction == "up" and r > 0) or (p.direction == "down" and r < 0)
    if p.direction == "flat" or not consistent:
        base = 0.0

    notes: list[str] = []
    extra_pos: list[str] = []
    extra_neg: list[str] = []
    if p.confidence_status == "calibrated" and p.confidence is not None:
        c = p.confidence
        factor = clamp((c - 0.5) / (cfg.prediction_confidence_full_at - 0.5), 0.0, 1.0)
        if c < 0.6:
            extra_neg.append(f"ML prediction confidence is low ({c * 100:.0f}%)")
    else:
        factor = cfg.prediction_uncalibrated_factor
        notes.append(
            "The ML model's confidence is not calibrated, so its prediction counts at "
            f"{factor * 100:.0f}% strength in the decision."
        )
        extra_neg.append("ML prediction confidence is unavailable (not calibrated)")
    if p.return_lower is not None and p.return_upper is not None and p.return_lower < 0 < p.return_upper:
        factor *= cfg.prediction_range_straddles_zero_factor
        extra_neg.append("The ML predicted return range includes zero, so the direction is uncertain")
    score = round(base * factor, 2)

    comps = [ComponentScore("predicted_return", score, 1.0,
                            f"The ML model predicts a {r * 100:+.2f}% return over {horizon}",
                            f"The ML model predicts a {r * 100:+.2f}% return over {horizon}")]
    module = ModuleSignal(key="prediction", usable=True, score=score, label=_label("prediction", score, cfg),
                          components=comps, extra_positive=extra_pos, extra_negative=extra_neg, notes=notes,
                          intra_agreement=None)
    return module


_SIGNAL_BUILDERS: dict[str, Callable[[DecisionInputs, DecisionConfig], ModuleSignal]] = {
    "technical": technical_signal,
    "fundamental": fundamental_signal,
    "sentiment": sentiment_signal,
    "prediction": prediction_signal,
}


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _effective_weights(signals: dict[str, ModuleSignal], cfg: DecisionConfig) -> dict[str, float]:
    return {k: cfg.module_weights.get(k, 0.0) * s.reliability for k, s in signals.items() if s.usable}


def _agreement(signals: dict[str, ModuleSignal], weights: dict[str, float], cfg: DecisionConfig) -> dict[str, Any]:
    bull = bear = neutral = 0.0
    n_bull = n_bear = n_neutral = 0
    for k, w in weights.items():
        s = signals[k].score or 0.0
        d = sign(s, cfg.agreement_sign_threshold)
        if d > 0:
            bull += w
            n_bull += 1
        elif d < 0:
            bear += w
            n_bear += 1
        else:
            neutral += w
            n_neutral += 1
    total = bull + bear + neutral
    cross = ((max(bull, bear) + 0.5 * neutral) / total) if total > 0 else None
    conflict = (min(bull, bear) / total) if total > 0 else 0.0
    intra_items = [(signals[k].intra_agreement, weights[k]) for k in weights if signals[k].intra_agreement is not None]
    intra = weighted_average(intra_items) if intra_items else None
    return {
        "cross_module": None if cross is None else round(cross, 4),
        "intra_module": None if intra is None else round(intra, 4),
        "conflict_share": round(conflict, 4),
        "conflicting": conflict >= cfg.conflict_share_threshold,
        "bullish_modules": n_bull,
        "bearish_modules": n_bear,
        "neutral_modules": n_neutral,
    }


def _confidence(
    signals: dict[str, ModuleSignal], weights: dict[str, float], agreement: dict[str, Any],
    risk: RiskResult, final_score: float, inputs: DecisionInputs, cfg: DecisionConfig,
) -> Optional[float]:
    # Agreement between modules is meaningless with a single module, so no confidence is claimed.
    if len(weights) < max(cfg.min_usable_modules, 2) or agreement["cross_module"] is None:
        return None
    base_total = sum(cfg.module_weights.values()) or 1.0
    usable_share = sum(cfg.module_weights.get(k, 0.0) for k in weights) / base_total
    parts: dict[str, float] = {
        "cross_module_agreement": agreement["cross_module"] * 100.0,
        "data_coverage": (usable_share + risk.coverage) / 2.0 * 100.0,
    }
    if agreement["intra_module"] is not None:
        parts["intra_module_agreement"] = agreement["intra_module"] * 100.0
    if signals["sentiment"].usable:
        parts["sentiment_reliability"] = signals["sentiment"].reliability * 100.0
    p = inputs.prediction
    if signals["prediction"].usable and p.confidence_status == "calibrated" and p.confidence is not None:
        parts["model_confidence"] = p.confidence * 100.0

    value = weighted_average((v, cfg.confidence_weights.get(k, 0.0)) for k, v in parts.items())
    if value is None:
        return None
    if agreement["conflicting"]:
        value -= cfg.conflict_confidence_penalty
    if final_score > 0 and risk.level is not None:
        value -= cfg.confidence_risk_penalty_by_level.get(risk.level, 0.0)
    return round(clamp(value, 0.0, 100.0), 1)


def _decide(
    final_score: float, risk: RiskResult, confidence: Optional[float], agreement: dict[str, Any], cfg: DecisionConfig,
) -> tuple[str, str, list[dict[str, str]]]:
    """(final decision, base decision before overrides, overrides that fired)."""
    if final_score >= cfg.buy_threshold:
        base = DECISION_BUY
    elif final_score <= cfg.sell_threshold:
        base = DECISION_SELL
    else:
        base = DECISION_HOLD
    decision = base
    fired: list[dict[str, str]] = []
    level = risk.level or ""

    # 1. Risk gate on BUY.
    if decision == DECISION_BUY:
        needed = cfg.buy_min_score_by_risk_level.get(level)
        if needed is not None and final_score < needed:
            decision = DECISION_HOLD
            fired.append({"rule": "risk_buy_gate", "description":
                          f"Risk is {level.replace('_', ' ').lower()}: a BUY needs a risk-adjusted score of at least "
                          f"{needed:+.0f} (this one is {final_score:+.1f}), so the decision is HOLD."})

    # 2. Conflict between modules + weak score.
    if decision in (DECISION_BUY, DECISION_SELL) and agreement["conflicting"] and abs(final_score) < cfg.conflict_hold_below_abs:
        fired.append({"rule": "signal_conflict", "description":
                      f"The analysis modules disagree and the score ({final_score:+.1f}) is weaker than "
                      f"±{cfg.conflict_hold_below_abs:.0f}, so the decision is HOLD."})
        decision = DECISION_HOLD

    # 3. Low confidence.
    if decision in (DECISION_BUY, DECISION_SELL) and (confidence is None or confidence < cfg.min_confidence_for_action):
        shown = "unavailable" if confidence is None else f"{confidence:.0f}%"
        fired.append({"rule": "low_confidence", "description":
                      f"Decision confidence ({shown}) is below the {cfg.min_confidence_for_action:.0f}% needed for a BUY or SELL, "
                      "so the decision is HOLD."})
        decision = DECISION_HOLD

    # 4. Risk-driven SELL escalation (only when nothing above fired and the base was HOLD).
    if base == DECISION_HOLD and decision == DECISION_HOLD and not fired:
        limit = cfg.sell_max_score_by_risk_level.get(level)
        if limit is not None and final_score <= limit and (confidence is not None and confidence >= cfg.min_confidence_for_action):
            decision = DECISION_SELL
            fired.append({"rule": "risk_sell_escalation", "description":
                          f"Risk is {level.replace('_', ' ').lower()}: a negative score of {limit:+.0f} or lower is enough "
                          f"for a SELL (this one is {final_score:+.1f})."})
    return decision, base, fired


# ---------------------------------------------------------------------------
# Data quality / status
# ---------------------------------------------------------------------------


def _data_quality(inputs: DecisionInputs, signals: dict[str, ModuleSignal], risk: RiskResult, cfg: DecisionConfig) -> dict[str, Any]:
    quality: dict[str, Any] = {}
    market = inputs.market.status
    quality["market"] = {"available": market.usable, "state": market.state, "reason": market.reason, "as_of": market.as_of}
    for key in MODULES:
        status = getattr(inputs, key).status
        sig = signals[key]
        state, reason = status.state, status.reason
        if status.usable and not sig.usable:
            state, reason = STATE_INSUFFICIENT, sig.reason
        quality[key] = {"available": sig.usable, "state": state, "reason": reason, "as_of": status.as_of}
    usable = [k for k in MODULES if signals[k].usable]
    base_total = sum(cfg.module_weights.values()) or 1.0
    quality["summary"] = {
        "usable_modules": usable,
        "module_coverage_percent": round(sum(cfg.module_weights.get(k, 0.0) for k in usable) / base_total * 100.0, 1),
        "risk_coverage_percent": round(risk.coverage * 100.0, 1),
        "prediction_available": signals["prediction"].usable,
    }
    return quality


def _gate(inputs: DecisionInputs, signals: dict[str, ModuleSignal], risk: RiskResult, cfg: DecisionConfig) -> Optional[tuple[str, str]]:
    """(status, reason) when no honest decision can be made, else None."""
    market = inputs.market.status
    if market.state == STATE_STALE:
        return STATUS_STALE_DATA, market.reason or "The market data snapshot is out of date."
    if not market.usable:
        return STATUS_INSUFFICIENT_DATA, market.reason or "No usable market data is available for this coin."
    if cfg.prediction_required and not signals["prediction"].usable:
        return STATUS_PREDICTION_UNAVAILABLE, signals["prediction"].reason or "The ML prediction is unavailable."

    usable = [k for k, s in signals.items() if s.usable]
    if len(usable) < cfg.min_usable_modules:
        states = [getattr(inputs, k).status.state for k in MODULES]
        if STATE_STALE in states:
            return STATUS_STALE_DATA, "Too much of the underlying analysis data is out of date to produce a decision."
        if not usable and STATE_UNAVAILABLE in states:
            return STATUS_ANALYSIS_UNAVAILABLE, "The analysis modules could not be loaded, so no decision can be produced."
        return STATUS_INSUFFICIENT_DATA, (
            f"Only {len(usable)} of the 4 analysis modules have usable data; at least {cfg.min_usable_modules} are required."
        )
    if not risk.available:
        return STATUS_INSUFFICIENT_DATA, risk.reason or "A risk score could not be established from the available data."
    return None


# ---------------------------------------------------------------------------
# Factors and explanation
# ---------------------------------------------------------------------------


def _collect_factors(signals: dict[str, ModuleSignal], weights: dict[str, float], risk: RiskResult,
                     engine: EngineConfig) -> tuple[list[str], list[str]]:
    """Factors that drove the decision come first (strongest first), then risk context (strongest first)."""
    cfg = engine.decision
    pos: list[tuple[float, str]] = []
    neg: list[tuple[float, str]] = []
    for key, sig in signals.items():
        if not sig.usable:
            continue
        mw = weights.get(key, 0.0)
        for c in sig.components:
            strength = abs(c.score) * c.weight * mw
            if c.score >= cfg.factor_component_threshold and c.positive_text:
                pos.append((strength, c.positive_text))
            elif c.score <= -cfg.factor_component_threshold and c.negative_text:
                neg.append((strength, c.negative_text))
        # Caveats about the evidence itself (e.g. low ML confidence) rank below the signals.
        neg += [(0.0, t) for t in sig.extra_negative]
        pos += [(0.0, t) for t in sig.extra_positive]
    risk_pos, risk_neg = risk_factor_items(risk.components, engine.risk)

    def order(items: list[tuple[float, str]], risk_items: list[tuple[float, str]]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        ranked = sorted(items, key=lambda it: (-it[0], it[1])) + risk_items  # risk_items are already strongest-first
        for _, text in ranked:
            if text not in seen:
                seen.add(text)
                out.append(text)
        return out[:MAX_FACTORS_PER_SIDE]

    return order(pos, risk_pos), order(neg, risk_neg)


def _pretty(level: Optional[str]) -> str:
    return (level or "").replace("_", " ").lower()


def _explain(res_decision: str, raw: float, final: float, risk: RiskResult, agreement: dict[str, Any],
             overrides: list[dict[str, str]], base: str, cfg: DecisionConfig, missing: list[str]) -> list[str]:
    lines = [
        f"Decision: {res_decision}. The combined signal score is {raw:+.1f}"
        + (f", {final:+.1f} after the risk adjustment" if abs(raw - final) >= 0.05 else "")
        + f" (BUY at {cfg.buy_threshold:+.0f} or higher, SELL at {cfg.sell_threshold:+.0f} or lower).",
        f"Risk is {_pretty(risk.level)} ({risk.score:.0f}/100).",
        f"{agreement['bullish_modules']} module(s) lean bullish, {agreement['bearish_modules']} bearish and "
        f"{agreement['neutral_modules']} neutral.",
    ]
    if base != res_decision or overrides:
        lines.append(f"Before overrides the score pointed to {base}.")
    lines += [o["description"] for o in overrides]
    if missing:
        lines.append("Not used in this decision: " + ", ".join(missing) + ".")
    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def evaluate(inputs: DecisionInputs, config: EngineConfig = DEFAULT_ENGINE_CONFIG) -> DecisionResult:
    """Run the full risk + decision calculation. Pure function of `inputs` and `config`."""
    cfg = config.decision
    signals = {k: build(inputs, cfg) for k, build in _SIGNAL_BUILDERS.items()}
    risk = calculate_risk(inputs, config.risk)
    risk.config_version = config.risk_config_version
    weights = _effective_weights(signals, cfg)
    quality = _data_quality(inputs, signals, risk, cfg)
    labels = {k: (s.label if s.usable else SIGNAL_UNAVAILABLE) for k, s in signals.items()}
    labels["risk"] = risk.level if risk.available and risk.level else SIGNAL_UNAVAILABLE
    scores = {k: (s.score if s.usable else None) for k, s in signals.items()}
    missing = [k for k, s in signals.items() if not s.usable]

    warnings: list[str] = []
    for k in missing:
        if k == "prediction":
            why = (signals[k].reason or "no usable prediction").rstrip(".")
            warnings.append(f"ML prediction unavailable ({why}). Decision calculated using the remaining available signals.")
        else:
            warnings.append(f"{k.capitalize()} unavailable: {signals[k].reason or 'no usable data'}")
    for s in signals.values():
        warnings += s.notes

    gate = _gate(inputs, signals, risk, cfg)
    if gate is not None:
        status, reason = gate
        return DecisionResult(
            status=status, status_reason=reason, decision=None, decision_score=None, raw_score=None, risk_adjustment=None,
            confidence=None, confidence_status="unavailable", base_decision=None, risk=risk, signals=labels,
            signal_scores=scores, effective_weights={k: round(v, 4) for k, v in weights.items()},
            positive_factors=[], negative_factors=[], overrides=[],
            agreement=_agreement(signals, weights, cfg), data_quality=quality, warnings=warnings,
            explanation=[f"No decision was produced: {reason}"],
            engine_version=config.engine_version, risk_config_version=config.risk_config_version,
        )

    raw = round(weighted_average((signals[k].score or 0.0, w) for k, w in weights.items()) or 0.0, 1)
    dampening = piecewise(risk.score or 0.0, cfg.risk_dampening_curve) if raw > 0 else 0.0
    final = round(raw * (1.0 - dampening), 1)
    agreement = _agreement(signals, weights, cfg)
    confidence = _confidence(signals, weights, agreement, risk, final, inputs, cfg)
    decision, base, overrides = _decide(final, risk, confidence, agreement, cfg)
    positive, negative = _collect_factors(signals, weights, risk, config)

    return DecisionResult(
        status=STATUS_VALID, status_reason=None, decision=decision, decision_score=final, raw_score=raw,
        risk_adjustment=round(final - raw, 1), confidence=confidence,
        confidence_status="computed" if confidence is not None else "unavailable",
        base_decision=base, risk=risk, signals=labels, signal_scores=scores,
        effective_weights={k: round(v, 4) for k, v in weights.items()},
        positive_factors=positive, negative_factors=negative, overrides=overrides, agreement=agreement,
        data_quality=quality, warnings=warnings,
        explanation=_explain(decision, raw, final, risk, agreement, overrides, base, cfg, missing),
        engine_version=config.engine_version, risk_config_version=config.risk_config_version,
    )


__all__ = [
    "ComponentScore", "DecisionResult", "ModuleSignal", "evaluate", "technical_signal", "fundamental_signal",
    "sentiment_signal", "prediction_signal",
]
