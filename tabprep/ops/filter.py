"""Row/class filtering ops."""
from __future__ import annotations

import pandas as pd

from tabprep.ops._registry import op


@op("filter_min_class_count")
def filter_min_class_count(df: pd.DataFrame, *, label_col: str,
                           min_count: int = 50) -> pd.DataFrame:
    """Drop rows whose label appears fewer than `min_count` times."""
    if label_col not in df.columns:
        raise KeyError(f"filter_min_class_count: label_col {label_col!r} not in dataframe")
    counts = df[label_col].value_counts()
    keep_labels = counts[counts >= int(min_count)].index
    return df[df[label_col].isin(keep_labels)].reset_index(drop=True)


@op("drop_classes")
def drop_classes(df: pd.DataFrame, *, label_col: str,
                 labels: list[str]) -> pd.DataFrame:
    """Drop rows whose label is in `labels`."""
    drop = set(str(x) for x in labels or [])
    if not drop:
        return df
    mask = ~df[label_col].astype(str).isin(drop)
    return df[mask].reset_index(drop=True)


@op("keep_classes")
def keep_classes(df: pd.DataFrame, *, label_col: str,
                 labels: list[str]) -> pd.DataFrame:
    """Keep only rows whose label is in `labels`."""
    keep = set(str(x) for x in labels or [])
    if not keep:
        return df
    mask = df[label_col].astype(str).isin(keep)
    return df[mask].reset_index(drop=True)
