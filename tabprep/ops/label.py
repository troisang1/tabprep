"""Label-related ops."""
from __future__ import annotations

import pandas as pd

from tabprep.ops._registry import op


@op("rename_label")
def rename_label(df: pd.DataFrame, *, label_col: str,
                 source_column: str, rename_to: str = "label") -> pd.DataFrame:
    """Rename `source_column` to `rename_to` (default 'label')."""
    if source_column == rename_to:
        return df
    if source_column not in df.columns:
        raise KeyError(f"rename_label: source_column {source_column!r} not in dataframe")
    return df.rename(columns={source_column: rename_to})


@op("normalize_label_string")
def normalize_label_string(df: pd.DataFrame, *, label_col: str,
                           method: str = "lowercase_underscore") -> pd.DataFrame:
    """Apply a deterministic string normalisation to the label column."""
    if label_col not in df.columns:
        raise KeyError(f"normalize_label_string: label_col {label_col!r} not in dataframe")
    out = df.copy()
    s = out[label_col].astype(str)
    if method == "lowercase_underscore":
        out[label_col] = (s.str.strip()
                          .str.lower()
                          .str.replace(" ", "_", regex=False)
                          .str.replace("-", "_", regex=False))
    elif method == "none":
        pass
    else:
        raise ValueError(f"unknown normalize method: {method!r}")
    return out
