"""Train / calibration / test split implementations."""
from __future__ import annotations

import pandas as pd


def stratified_class_balanced(
    df: pd.DataFrame,
    *,
    label_col: str,
    train_frac: float,
    cal_frac: float,
    test_frac: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split each class into train/cal/test by the given fractions, then
    concatenate. Per-class shuffle uses `seed` so the split is deterministic.
    """
    if abs(train_frac + cal_frac + test_frac - 1.0) > 1e-3:
        raise ValueError("split fractions must sum to 1.0")

    train_parts: list[pd.DataFrame] = []
    cal_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []

    # Sort labels for determinism — `groupby(sort=True)` is also enough on
    # newer pandas, but being explicit makes the contract obvious.
    for label, group in df.groupby(label_col, sort=True):
        n = len(group)
        shuffled = group.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        n_tr = max(1, int(n * train_frac))
        n_ca = max(1, int(n * cal_frac))
        train_parts.append(shuffled.iloc[:n_tr])
        cal_parts.append(shuffled.iloc[n_tr:n_tr + n_ca])
        test_parts.append(shuffled.iloc[n_tr + n_ca:])

    def _concat(parts: list[pd.DataFrame]) -> pd.DataFrame:
        return (
            pd.concat(parts, ignore_index=True)
            .sample(frac=1.0, random_state=seed)
            .reset_index(drop=True)
        )

    return _concat(train_parts), _concat(cal_parts), _concat(test_parts)


_SPLIT_KINDS = {
    "stratified_class_balanced": stratified_class_balanced,
}


def run_split(df: pd.DataFrame, *, label_col: str, kind: str, train_frac: float,
              cal_frac: float, test_frac: float, seed: int):
    fn = _SPLIT_KINDS.get(kind)
    if fn is None:
        raise ValueError(f"unknown split kind: {kind!r}")
    return fn(
        df,
        label_col=label_col,
        train_frac=train_frac,
        cal_frac=cal_frac,
        test_frac=test_frac,
        seed=seed,
    )
