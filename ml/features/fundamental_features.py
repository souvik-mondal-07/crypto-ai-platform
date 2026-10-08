"""Fundamental features.

IMPORTANT — why these are not training features by default
---------------------------------------------------------
Phase 11 fundamentals are computed from the *current* ``market_data`` snapshot
(market cap, FDV, supply, ATH/ATL distance, rank). The platform stores no history
of those values. Attaching today's snapshot to every historical training row would
leak present-day information into the past (e.g. "ATH distance" would already
contain the future price path), so these features are:

* implemented here so they are ready the moment point-in-time history exists;
* excluded from training and prediction unless ``FeatureConfig.include_fundamental_snapshot``
  is set (and then only by a caller that has point-in-time data).

Missing inputs yield ``NaN`` — never a guessed value.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional

FUNDAMENTAL_SNAPSHOT_FEATURES = (
    "fund_market_cap_log",
    "fund_fdv_log",
    "fund_volume_to_market_cap",
    "fund_circulating_to_total_supply",
    "fund_circulating_to_max_supply",
    "fund_ath_distance",
    "fund_atl_distance",
    "fund_market_rank",
)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> float:
    if numerator is None or denominator is None or denominator <= 0:
        return math.nan
    return numerator / denominator


def snapshot_fundamental_features(snapshot: Mapping[str, Any]) -> dict[str, float]:
    """Features from one ``market_data`` document (current snapshot)."""
    market_cap = _num(snapshot.get("market_cap_usd"))
    fdv = _num(snapshot.get("fully_diluted_valuation_usd"))
    volume = _num(snapshot.get("volume_24h_usd"))
    circulating = _num(snapshot.get("circulating_supply"))
    total = _num(snapshot.get("total_supply"))
    max_supply = _num(snapshot.get("max_supply"))
    price = _num(snapshot.get("price_usd"))
    ath = _num(snapshot.get("ath_usd"))
    atl = _num(snapshot.get("atl_usd"))
    rank = _num(snapshot.get("market_cap_rank"))

    return {
        "fund_market_cap_log": math.log(market_cap) if market_cap and market_cap > 0 else math.nan,
        "fund_fdv_log": math.log(fdv) if fdv and fdv > 0 else math.nan,
        "fund_volume_to_market_cap": _ratio(volume, market_cap),
        "fund_circulating_to_total_supply": _ratio(circulating, total),
        "fund_circulating_to_max_supply": _ratio(circulating, max_supply),
        "fund_ath_distance": (price / ath - 1.0) if price and ath and ath > 0 else math.nan,
        "fund_atl_distance": (price / atl - 1.0) if price and atl and atl > 0 else math.nan,
        "fund_market_rank": rank if rank is not None and rank > 0 else math.nan,
    }
