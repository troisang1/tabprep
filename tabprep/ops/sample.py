"""Sampling / capping ops."""
from __future__ import annotations

import math

import pandas as pd

from tabprep.ops._registry import op


@op("cap_per_class")
def cap_per_class(df: pd.DataFrame, *, label_col: str, cap: int,
                  seed: int = 42) -> pd.DataFrame:
    """Subsample each class to at most `cap` rows. Deterministic by seed."""
    return (
        df.groupby(label_col, group_keys=False, sort=True)
          .apply(lambda x: x.sample(n=min(len(x), int(cap)), random_state=int(seed)))
          .reset_index(drop=True)
    )


@op("balanced_subsample")
def balanced_subsample(df: pd.DataFrame, *, label_col: str, max_total: int,
                       seed: int = 42) -> pd.DataFrame:
    """Cap the dataset to at most `max_total` rows by per-class subsampling
    such that every class has the same target size.
    """
    n_classes = df[label_col].nunique()
    if n_classes == 0:
        return df
    n_per = max(1, int(max_total) // int(n_classes))
    return cap_per_class(df, label_col=label_col, cap=n_per, seed=seed)


@op("stratified_fraction_sample")
def stratified_fraction_sample(df: pd.DataFrame, *, label_col: str,
                               fraction: float, seed: int = 42) -> pd.DataFrame:
    """Take `fraction` of each class — preserves the original distribution.

    Distinct from `balanced_subsample`: this op DOES NOT rebalance. Each
    class keeps `floor(fraction * n_class)` rows with a floor of 1, so
    a class with even a single sample is never silently dropped. The
    resulting frame has roughly the same class proportions as the input.

    Used as the standard "give me a 5% slice for benchmark experiments"
    op across every profile in the framework — large datasets become
    tractable, small datasets stay representative, and (unlike
    balanced_subsample) the per-class proportions match upstream.

    Parameters
    ----------
    fraction
        Proportion in (0, 1].
    seed
        Determines the per-class shuffle and the post-concat reshuffle
        so the row order does not reveal the per-class block structure.
    """
    if not 0 < fraction <= 1:
        raise ValueError(f"fraction must be in (0, 1] (got {fraction})")
    if label_col not in df.columns:
        raise KeyError(f"stratified_fraction_sample: label_col {label_col!r} not in dataframe")

    parts: list[pd.DataFrame] = []
    for _label, group in df.groupby(label_col, sort=True):
        n = len(group)
        if n == 0:
            continue
        k = max(1, int(math.floor(n * float(fraction))))
        shuffled = group.sample(frac=1.0, random_state=int(seed)).reset_index(drop=True)
        parts.append(shuffled.iloc[:k])

    if not parts:
        return df.iloc[0:0].copy()

    out = pd.concat(parts, ignore_index=True)
    return out.sample(frac=1.0, random_state=int(seed)).reset_index(drop=True)
