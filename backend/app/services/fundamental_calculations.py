"""
Fundamental-analysis calculations (Phase 11) — pure functions only.

No I/O, no MongoDB, no HTTP, and deliberately no third-party imports:
everything here takes plain values in and returns plain dataclasses out,
which is what makes each rule independently unit-testable
(tests/test_fundamental_calculations.py) and keeps the FastAPI layer free
of business logic.

Three things live here, kept separate on purpose:

1. DERIVED METRICS — arithmetic on provider-reported values (volume /
   market cap, circulating / max supply, distance from ATH, ...). A
   metric is `None` with an `unavailable_reason` whenever an input is
   missing or mathematically invalid; nothing is ever assumed or
   substituted. These are CALCULATED values and are labelled as such all
   the way to the UI — they are never presented as provider-reported.

2. THE FUNDAMENTAL SCORE — a transparent, rule-based 0-100 score. Every
   component has a fixed weight, fixed threshold bands, and reports its
   own input and rule, so the number can be reproduced by hand. See
   docs/fundamental-analysis.md. It is a structural descriptor only:
   it is NOT a BUY/HOLD/SELL signal (that is a later phase) and it
   deliberately excludes price action (ATH drawdown, recent
   performance).

3. THE SUMMARY — short factual sentences generated from the metrics by
   fixed templates. No predictions, no recommendations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

SCORE_METHOD_VERSION = "1.0"

#: Minimum share of total score weight that must be backed by real data
#: before any score is shown, and the minimum number of components.
MIN_SCORE_COVERAGE_PERCENT = 50.0
MIN_SCORE_COMPONENTS = 3

SCORE_DISCLAIMER = (
    "A descriptive, rule-based summary of structural characteristics. It is "
    "not investment advice, does not predict price movements, and is not a "
    "trading signal or decision."
)

NOT_ENOUGH_DATA_MESSAGE = "Not enough data"

SupplyType = Literal["capped", "unlimited", "not_reported"]
MetricUnit = Literal["ratio", "percent", "tokens"]


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------


def valid_number(value: Any) -> Optional[float]:
    """A finite float, or None. Rejects bool, NaN, inf, strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _positive(value: Any) -> Optional[float]:
    number = valid_number(value)
    return number if number is not None and number > 0 else None


def _non_negative(value: Any) -> Optional[float]:
    number = valid_number(value)
    return number if number is not None and number >= 0 else None


# ---------------------------------------------------------------------------
# 1. Derived metrics
# ---------------------------------------------------------------------------


@dataclass
class CalculatedMetric:
    value: Optional[float]
    unit: MetricUnit
    formula: str
    unavailable_reason: Optional[str] = None


@dataclass
class CalculatedMetrics:
    volume_to_market_cap: CalculatedMetric
    market_cap_to_fdv: CalculatedMetric
    circulating_to_max_supply_percent: CalculatedMetric
    remaining_to_max_supply_percent: CalculatedMetric
    remaining_supply_to_max: CalculatedMetric
    circulating_to_total_supply_percent: CalculatedMetric
    distance_from_ath_percent: CalculatedMetric
    distance_from_atl_percent: CalculatedMetric


def _metric(value: Optional[float], unit: MetricUnit, formula: str, reason: Optional[str]) -> CalculatedMetric:
    if value is not None:
        return CalculatedMetric(value=value, unit=unit, formula=formula, unavailable_reason=None)
    return CalculatedMetric(value=None, unit=unit, formula=formula, unavailable_reason=reason)


def compute_metrics(
    *,
    price_usd: Any,
    market_cap_usd: Any,
    volume_24h_usd: Any,
    circulating_supply: Any,
    total_supply: Any,
    max_supply: Any,
    fully_diluted_valuation_usd: Any,
    ath_usd: Any,
    atl_usd: Any,
) -> CalculatedMetrics:
    """
    Derive every calculated metric from provider-reported inputs.

    Each metric checks exactly the preconditions that make its formula
    mathematically valid, and states the reason when they aren't met.
    """
    price = _non_negative(price_usd)
    market_cap = _positive(market_cap_usd)
    volume = _non_negative(volume_24h_usd)
    circulating = _non_negative(circulating_supply)
    total = _positive(total_supply)
    max_sup = _positive(max_supply)
    fdv = _positive(fully_diluted_valuation_usd)
    ath = _positive(ath_usd)
    atl = _positive(atl_usd)

    # --- Volume / Market Cap ------------------------------------------------
    vol_mc: Optional[float] = None
    vol_mc_reason: Optional[str] = None
    if volume is None:
        vol_mc_reason = "24h volume is not available."
    elif market_cap is None:
        vol_mc_reason = "Market cap is not available (or is zero)."
    else:
        vol_mc = volume / market_cap

    # --- Market Cap / FDV ---------------------------------------------------
    mc_fdv: Optional[float] = None
    mc_fdv_reason: Optional[str] = None
    if market_cap is None:
        mc_fdv_reason = "Market cap is not available (or is zero)."
    elif fdv is None:
        mc_fdv_reason = "Fully diluted valuation is not available."
    else:
        ratio = market_cap / fdv
        # FDV can't legitimately be below market cap. A small overshoot
        # is snapshot timing between fields; a large one is bad data.
        if ratio > 1.01:
            mc_fdv_reason = "Market cap exceeds fully diluted valuation (provider data inconsistent)."
        else:
            mc_fdv = ratio

    # --- Supply ratios ------------------------------------------------------
    circ_max: Optional[float] = None
    remaining_pct: Optional[float] = None
    remaining_tokens: Optional[float] = None
    max_reason: Optional[str] = None
    if circulating is None:
        max_reason = "Circulating supply is not available."
    elif max_sup is None:
        max_reason = "Maximum supply is not reported (unlimited or unknown)."
    elif circulating > max_sup:
        max_reason = "Circulating supply exceeds the reported maximum supply (provider data inconsistent)."
    else:
        circ_max = circulating / max_sup * 100.0
        remaining_pct = 100.0 - circ_max
        remaining_tokens = max_sup - circulating

    circ_total: Optional[float] = None
    total_reason: Optional[str] = None
    if circulating is None:
        total_reason = "Circulating supply is not available."
    elif total is None:
        total_reason = "Total supply is not available."
    elif circulating > total:
        total_reason = "Circulating supply exceeds the reported total supply (provider data inconsistent)."
    else:
        circ_total = circulating / total * 100.0

    # --- Distance from ATH / ATL -------------------------------------------
    from_ath: Optional[float] = None
    ath_reason: Optional[str] = None
    if price is None:
        ath_reason = "Current price is not available."
    elif ath is None:
        ath_reason = "All-time high is not available."
    else:
        from_ath = (price / ath - 1.0) * 100.0

    from_atl: Optional[float] = None
    atl_reason: Optional[str] = None
    if price is None:
        atl_reason = "Current price is not available."
    elif atl is None:
        atl_reason = "All-time low is not available (or is zero)."
    else:
        from_atl = (price / atl - 1.0) * 100.0

    return CalculatedMetrics(
        volume_to_market_cap=_metric(vol_mc, "ratio", "24h volume / market cap", vol_mc_reason),
        market_cap_to_fdv=_metric(mc_fdv, "ratio", "market cap / fully diluted valuation", mc_fdv_reason),
        circulating_to_max_supply_percent=_metric(
            circ_max, "percent", "circulating supply / max supply x 100", max_reason
        ),
        remaining_to_max_supply_percent=_metric(
            remaining_pct, "percent", "(max supply - circulating supply) / max supply x 100", max_reason
        ),
        remaining_supply_to_max=_metric(
            remaining_tokens, "tokens", "max supply - circulating supply", max_reason
        ),
        circulating_to_total_supply_percent=_metric(
            circ_total, "percent", "circulating supply / total supply x 100", total_reason
        ),
        distance_from_ath_percent=_metric(
            from_ath, "percent", "(current price / all-time high - 1) x 100", ath_reason
        ),
        distance_from_atl_percent=_metric(
            from_atl, "percent", "(current price / all-time low - 1) x 100", atl_reason
        ),
    )


# ---------------------------------------------------------------------------
# Supply classification
# ---------------------------------------------------------------------------


def classify_supply(
    max_supply: Any, max_supply_infinite: Optional[bool]
) -> tuple[SupplyType, list[str]]:
    """
    Returns (supply_type, data-quality notes).

    - "capped": a positive maximum supply is reported.
    - "unlimited": the provider EXPLICITLY flags the supply as infinite.
    - "not_reported": no maximum supply and no explicit flag. A null
      max supply on its own is ambiguous (unlimited or simply unknown),
      so it is never promoted to "unlimited" on assumption.
    """
    notes: list[str] = []
    max_sup = _positive(max_supply)
    if max_sup is not None:
        if max_supply_infinite is True:
            notes.append("Provider reports both a maximum supply and an infinite-supply flag; the maximum supply is used.")
        return "capped", notes
    if max_supply_infinite is True:
        return "unlimited", notes
    return "not_reported", notes


# ---------------------------------------------------------------------------
# 2. Fundamental score
# ---------------------------------------------------------------------------


@dataclass
class ScoreComponent:
    key: str
    label: str
    weight: int
    available: bool
    subscore: Optional[float]
    points: Optional[float]
    input_description: str
    rule: str


@dataclass
class FundamentalScoreResult:
    status: Literal["scored", "not_enough_data"]
    score: Optional[float]
    coverage_percent: float
    components: list[ScoreComponent]
    method_version: str = SCORE_METHOD_VERSION
    min_coverage_percent: float = MIN_SCORE_COVERAGE_PERCENT
    message: Optional[str] = None
    disclaimer: str = SCORE_DISCLAIMER


@dataclass
class DevelopmentInput:
    """Provider-reported development figures used by the score."""

    github_repo_count: int = 0
    stars: Optional[int] = None
    forks: Optional[int] = None
    subscribers: Optional[int] = None
    total_issues: Optional[int] = None
    pull_request_contributors: Optional[int] = None
    commit_count_4_weeks: Optional[int] = None


@dataclass
class ScoreInputs:
    market_cap_usd: Optional[float]
    metrics: CalculatedMetrics
    #: None when no project profile has been obtained at all.
    profile_present: bool = False
    has_description: bool = False
    has_homepage: bool = False
    has_whitepaper: bool = False
    has_explorer: bool = False
    has_repository: bool = False
    has_categories: bool = False
    genesis_date: Optional[str] = None
    development: DevelopmentInput = field(default_factory=DevelopmentInput)


def development_data_available(dev: DevelopmentInput) -> bool:
    """
    Development data counts as real only if a GitHub repository is
    linked AND the provider reported at least one non-zero activity
    figure. CoinGecko returns all-zero developer blocks for coins whose
    repositories it doesn't track; scoring that as "0 commits" would
    present a data gap as if it were measured inactivity.
    """
    if dev.github_repo_count <= 0:
        return False
    figures = (
        dev.stars, dev.forks, dev.subscribers, dev.total_issues,
        dev.pull_request_contributors, dev.commit_count_4_weeks,
    )
    return any(isinstance(v, int) and v > 0 for v in figures)


def _band(value: float, bands: list[tuple[float, float]], floor: float) -> float:
    """First band whose lower bound `value` meets (bands sorted high->low), else `floor`."""
    for lower_bound, points in bands:
        if value >= lower_bound:
            return points
    return floor


def _fmt_usd(value: float) -> str:
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= threshold:
            return f"${value / threshold:,.2f}{suffix}"
    return f"${value:,.2f}"


def _parse_genesis_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def compute_fundamental_score(inputs: ScoreInputs, today: Optional[date] = None) -> FundamentalScoreResult:
    """
    Weighted average of the sub-scores that real data supports.

    Score = sum(weight_i x subscore_i) / sum(weight_i)   over AVAILABLE
    components, so a missing input never drags the score to zero — it
    just lowers `coverage_percent`. If available weight is below
    MIN_SCORE_COVERAGE_PERCENT or fewer than MIN_SCORE_COMPONENTS
    components are available, no score is produced.
    """
    today = today or datetime.now(timezone.utc).date()
    m = inputs.metrics
    components: list[ScoreComponent] = []

    def add(key: str, label: str, weight: int, subscore: Optional[float], described: str, rule: str) -> None:
        available = subscore is not None
        components.append(
            ScoreComponent(
                key=key, label=label, weight=weight, available=available,
                subscore=round(subscore, 1) if subscore is not None else None,
                points=round(weight * subscore / 100.0, 2) if subscore is not None else None,
                input_description=described, rule=rule,
            )
        )

    # (1) Market size — weight 25
    mc = _positive(inputs.market_cap_usd)
    add(
        "market_size", "Market size", 25,
        _band(mc, [(1e10, 100), (1e9, 80), (1e8, 60), (1e7, 40), (1e6, 20)], 10) if mc is not None else None,
        f"Market cap {_fmt_usd(mc)}" if mc is not None else "Market cap not available",
        "Market cap >= $10B: 100; >= $1B: 80; >= $100M: 60; >= $10M: 40; >= $1M: 20; otherwise 10.",
    )

    # (2) Liquidity — weight 20 (24h volume / market cap)
    ratio = m.volume_to_market_cap.value
    if ratio is None:
        liquidity = None
    elif ratio < 0.005:
        liquidity = 20.0
    elif ratio < 0.02:
        liquidity = 50.0
    elif ratio < 0.10:
        liquidity = 100.0
    elif ratio < 0.30:
        liquidity = 80.0
    else:
        liquidity = 50.0
    add(
        "liquidity", "Trading liquidity", 20, liquidity,
        f"24h volume is {ratio * 100:.2f}% of market cap" if ratio is not None else "Volume / market cap not available",
        "Volume/market cap < 0.5%: 20; < 2%: 50; < 10%: 100; < 30%: 80; >= 30%: 50 "
        "(very low turnover suggests thin trading; very high turnover suggests speculative churn).",
    )

    # (3) Supply dilution — weight 20 (circulating/max, else market cap/FDV)
    circ_pct = m.circulating_to_max_supply_percent.value
    fdv_ratio = m.market_cap_to_fdv.value
    supply_bands = [(90.0, 100), (75.0, 85), (50.0, 65), (25.0, 40)]
    if circ_pct is not None:
        supply_sub: Optional[float] = _band(circ_pct, supply_bands, 20)
        supply_desc = f"{circ_pct:.1f}% of maximum supply is circulating"
    elif fdv_ratio is not None:
        supply_sub = _band(fdv_ratio * 100.0, supply_bands, 20)
        supply_desc = f"Market cap is {fdv_ratio * 100:.1f}% of fully diluted valuation (no maximum supply used)"
    else:
        supply_sub = None
        supply_desc = "Neither circulating/max supply nor market cap/FDV available"
    add(
        "supply_dilution", "Supply in circulation", 20, supply_sub, supply_desc,
        "Share of eventual supply already circulating (circulating/max supply; if no max supply is "
        "reported, market cap/FDV instead): >= 90%: 100; >= 75%: 85; >= 50%: 65; >= 25%: 40; otherwise 20.",
    )

    # (4) Development activity — weight 15
    dev = inputs.development
    if development_data_available(dev) and isinstance(dev.commit_count_4_weeks, int):
        commits = dev.commit_count_4_weeks
        dev_sub: Optional[float] = _band(float(commits), [(100, 100), (30, 75), (10, 50), (1, 25)], 0)
        dev_desc = f"{commits} commits in the last 4 weeks across linked repositories (provider-reported)"
    else:
        dev_sub = None
        dev_desc = "No usable development data reported by the provider"
    add(
        "development_activity", "Development activity", 15, dev_sub, dev_desc,
        "Provider-reported commits in the last 4 weeks: >= 100: 100; >= 30: 75; >= 10: 50; >= 1: 25; 0: 0. "
        "Only scored when a GitHub repository is linked and the provider reports non-zero activity figures.",
    )

    # (5) Project maturity — weight 10 (age from provider genesis date)
    genesis = _parse_genesis_date(inputs.genesis_date)
    age_years = (today - genesis).days / 365.25 if genesis is not None and genesis <= today else None
    add(
        "project_maturity", "Project maturity", 10,
        _band(age_years, [(5, 100), (2, 75), (1, 50), (0.5, 25)], 10) if age_years is not None else None,
        f"{age_years:.1f} years since the provider-reported genesis date" if age_years is not None
        else "Genesis date not reported",
        "Years since genesis date: >= 5: 100; >= 2: 75; >= 1: 50; >= 0.5: 25; otherwise 10.",
    )

    # (6) Information completeness — weight 10
    if inputs.profile_present:
        checks = [
            inputs.has_description, inputs.has_homepage, inputs.has_whitepaper,
            inputs.has_explorer, inputs.has_repository, inputs.has_categories,
        ]
        present = sum(1 for c in checks if c)
        info_sub: Optional[float] = present / len(checks) * 100.0
        info_desc = f"{present} of {len(checks)} project-information items provided"
    else:
        info_sub = None
        info_desc = "Project profile not available"
    add(
        "information_completeness", "Project information", 10, info_sub, info_desc,
        "Share of six items the provider lists (description, website, whitepaper, block explorer, "
        "code repository, categories) x 100.",
    )

    available = [c for c in components if c.available]
    coverage = float(sum(c.weight for c in available))
    if coverage < MIN_SCORE_COVERAGE_PERCENT or len(available) < MIN_SCORE_COMPONENTS:
        return FundamentalScoreResult(
            status="not_enough_data", score=None, coverage_percent=coverage,
            components=components, message=NOT_ENOUGH_DATA_MESSAGE,
        )

    weighted = sum(c.weight * (c.subscore or 0.0) for c in available)
    return FundamentalScoreResult(
        status="scored", score=round(weighted / coverage, 1),
        coverage_percent=coverage, components=components,
    )


# ---------------------------------------------------------------------------
# 3. Factual summary
# ---------------------------------------------------------------------------

SummaryCategory = Literal["market_position", "liquidity", "supply", "valuation", "project", "development"]


@dataclass
class SummaryItem:
    category: SummaryCategory
    text: str


def build_summary(
    *,
    market_cap_rank: Optional[int],
    market_cap_usd: Any,
    supply_type: SupplyType,
    max_supply: Any,
    metrics: CalculatedMetrics,
    categories: list[str],
    asset_platform_id: Optional[str],
    genesis_date: Optional[str],
    github_repo_count: int,
    development: DevelopmentInput,
    market_present: bool = True,
    profile_present: bool = True,
) -> list[SummaryItem]:
    """
    Plain factual statements from available data only. Fixed templates,
    no adjectives that imply a recommendation, no forward-looking claims.
    A statement is omitted (never guessed) when its inputs are missing —
    in particular, an absent market snapshot or project profile produces
    NO supply / repository statement, so a data gap is never phrased as
    a fact ("no repository is linked", "supply cap is unknown").
    """
    items: list[SummaryItem] = []
    mc = _positive(market_cap_usd)

    if mc is not None and market_cap_rank is not None:
        items.append(SummaryItem("market_position", f"Ranked #{market_cap_rank} by market capitalization, with a market cap of {_fmt_usd(mc)}."))
    elif mc is not None:
        items.append(SummaryItem("market_position", f"Market capitalization is {_fmt_usd(mc)}."))
    elif market_cap_rank is not None:
        items.append(SummaryItem("market_position", f"Ranked #{market_cap_rank} by market capitalization."))

    ratio = metrics.volume_to_market_cap.value
    if ratio is not None:
        items.append(SummaryItem("liquidity", f"24h trading volume is {ratio * 100:.2f}% of market cap (calculated)."))

    circ_pct = metrics.circulating_to_max_supply_percent.value
    if not market_present:
        pass
    elif supply_type == "capped":
        cap = _positive(max_supply)
        if circ_pct is not None and cap is not None:
            items.append(SummaryItem("supply", f"Supply is capped at {cap:,.0f} units; {circ_pct:.1f}% is currently in circulation (calculated)."))
        elif cap is not None:
            items.append(SummaryItem("supply", f"Supply is capped at {cap:,.0f} units."))
    elif supply_type == "unlimited":
        items.append(SummaryItem("supply", "The provider reports no maximum supply limit (unlimited supply)."))
    else:
        items.append(SummaryItem("supply", "The provider does not report a maximum supply, so the supply cap is unknown."))

    fdv_ratio = metrics.market_cap_to_fdv.value
    if fdv_ratio is not None:
        items.append(SummaryItem("supply", f"Market cap is {fdv_ratio * 100:.1f}% of fully diluted valuation (calculated)."))

    from_ath = metrics.distance_from_ath_percent.value
    if from_ath is not None:
        if from_ath >= 0:
            items.append(SummaryItem("valuation", "Price is at or above the recorded all-time high (calculated)."))
        else:
            items.append(SummaryItem("valuation", f"Price is {abs(from_ath):.1f}% below its recorded all-time high (calculated)."))

    from_atl = metrics.distance_from_atl_percent.value
    if from_atl is not None:
        items.append(SummaryItem("valuation", f"Price is {from_atl:,.1f}% above its recorded all-time low (calculated)."))

    if not profile_present:
        return items

    if categories:
        items.append(SummaryItem("project", f"Listed under: {', '.join(categories[:4])}."))
    if asset_platform_id:
        items.append(SummaryItem("project", f"Issued as a token on the {asset_platform_id} platform."))
    if genesis_date:
        items.append(SummaryItem("project", f"Provider-reported genesis date: {genesis_date}."))

    if development_data_available(development) and development.commit_count_4_weeks is not None:
        items.append(SummaryItem(
            "development",
            f"{github_repo_count} linked repositor{'y' if github_repo_count == 1 else 'ies'}; "
            f"{development.commit_count_4_weeks} commits in the last 4 weeks (provider-reported).",
        ))
    elif github_repo_count > 0:
        items.append(SummaryItem("development", f"{github_repo_count} linked repositor{'y' if github_repo_count == 1 else 'ies'}; the provider reports no activity figures for them."))
    else:
        items.append(SummaryItem("development", "No code repository is linked by the provider."))

    return items
