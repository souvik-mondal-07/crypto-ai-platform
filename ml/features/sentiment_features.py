"""Sentiment features from REAL stored, analyzed news articles (Phase 12).

Point-in-time rule: the feature row for a candle uses only articles whose
``published_at`` is <= the candle's *close* time (``as_of``). Articles published
later are invisible to that row. Where fewer than ``min_articles`` articles fall
in the window, the feature is ``NaN`` — consistent with Phase 12's
"insufficient_data" behaviour — never a neutral placeholder.

Caveat (documented, not hidden): the news collection only contains history from
when ingestion started. For older candles most sentiment values are NaN and the
dataset builder drops the whole sentiment group when its coverage in the training
window is below ``MLConfig.min_feature_coverage``.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from ml.config.feature_config import FeatureConfig

SENTIMENT_FEATURE_NAMES = (
    "sent_score",
    "sent_positive_pct",
    "sent_neutral_pct",
    "sent_negative_pct",
    "sent_trend",
    "sent_news_volume",
)


def articles_frame(articles: Optional[Iterable[dict]]) -> pd.DataFrame:
    """Normalise ``[{published_at, label, score}, ...]`` to a sorted frame."""
    cols = ["published_at", "label", "score"]
    if articles is None:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(list(articles))
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = df[cols].copy()
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["published_at", "score"])
    return df.sort_values("published_at").reset_index(drop=True)


def build_sentiment_features(
    as_of: pd.Series,
    articles: Optional[Iterable[dict]],
    cfg: FeatureConfig = FeatureConfig(),
) -> pd.DataFrame:
    """One feature row per ``as_of`` timestamp (candle close time)."""
    n = len(as_of)
    out = pd.DataFrame(np.nan, index=as_of.index, columns=list(SENTIMENT_FEATURE_NAMES), dtype="float64")
    df = articles_frame(articles)
    if df.empty or n == 0:
        return out

    ts = df["published_at"].astype("int64").to_numpy()  # ns since epoch (UTC)
    score = df["score"].to_numpy(dtype="float64")
    label = df["label"].astype(str).to_numpy()
    csum = np.concatenate([[0.0], np.cumsum(score)])
    cpos = np.concatenate([[0], np.cumsum(label == "positive")])
    cneu = np.concatenate([[0], np.cumsum(label == "neutral")])
    cneg = np.concatenate([[0], np.cumsum(label == "negative")])

    window = int(cfg.sentiment_window_hours * 3600 * 1e9)
    asof_ns = pd.to_datetime(as_of, utc=True).astype("int64").to_numpy()

    # searchsorted(side="right") -> count of articles with published_at <= bound.
    hi = np.searchsorted(ts, asof_ns, side="right")
    lo = np.searchsorted(ts, asof_ns - window, side="right")        # (as_of - window, as_of]
    lo_prev = np.searchsorted(ts, asof_ns - 2 * window, side="right")  # previous window

    count = hi - lo
    prev_count = lo - lo_prev
    enough = count >= cfg.sentiment_min_articles
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = (csum[hi] - csum[lo]) / count
        prev_mean = (csum[lo] - csum[lo_prev]) / prev_count
        out["sent_score"] = np.where(enough, mean, np.nan)
        out["sent_positive_pct"] = np.where(enough, (cpos[hi] - cpos[lo]) / count * 100.0, np.nan)
        out["sent_neutral_pct"] = np.where(enough, (cneu[hi] - cneu[lo]) / count * 100.0, np.nan)
        out["sent_negative_pct"] = np.where(enough, (cneg[hi] - cneg[lo]) / count * 100.0, np.nan)
        out["sent_trend"] = np.where(enough & (prev_count >= cfg.sentiment_min_articles), mean - prev_mean, np.nan)
    # News volume is a plain count (0 is a real observation once any history exists).
    first_article_ns = ts[0]
    out["sent_news_volume"] = np.where(asof_ns >= first_article_ns, count.astype("float64"), np.nan)
    return out
