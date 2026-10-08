"""Chronological splitting and walk-forward folds. Never shuffles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class ChronologicalSplit:
    """Index ranges into a time-ordered dataset. train < validation < test, with an
    embargo gap between segments."""

    train: slice
    validation: slice
    test: slice
    embargo: int

    def sizes(self) -> dict[str, int]:
        return {k: len(range(*getattr(self, k).indices(10**12))) for k in ("train", "validation", "test")}


def chronological_split(n: int, train_fraction: float, validation_fraction: float, embargo: int = 0) -> ChronologicalSplit:
    """Split ``n`` time-ordered rows into train / validation / test.

    ``embargo`` rows are skipped after the train and validation segments. A row's
    target looks ``steps`` candles ahead, so without the gap the last training
    targets would overlap the first validation (and validation->test) period.
    """
    if n <= 0:
        raise ValueError("Cannot split an empty dataset.")
    if embargo < 0:
        raise ValueError("embargo must be >= 0")
    train_end = int(n * train_fraction)
    val_end = int(n * (train_fraction + validation_fraction))
    train = slice(0, train_end)
    validation = slice(train_end + embargo, val_end)
    test = slice(val_end + embargo, n)
    split = ChronologicalSplit(train, validation, test, embargo)
    if min(split.sizes().values()) <= 0:
        raise ValueError(f"Dataset of {n} rows is too small to split with embargo={embargo}.")
    return split


def walk_forward_splits(
    n: int, n_splits: int, min_train: int, test_size: int, embargo: int = 0
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window walk-forward folds: train on [0, a), test on [a+embargo, a+embargo+test_size)."""
    if n_splits < 1 or min_train < 1 or test_size < 1:
        raise ValueError("n_splits, min_train and test_size must be >= 1")
    last_start = n - test_size - embargo
    if last_start < min_train:
        raise ValueError("Not enough rows for the requested walk-forward configuration.")
    starts = np.linspace(min_train, last_start, num=n_splits).astype(int)
    for a in starts:
        yield np.arange(0, a), np.arange(a + embargo, min(a + embargo + test_size, n))
