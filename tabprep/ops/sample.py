"""Sampling / capping ops."""
from __future__ import annotations

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
