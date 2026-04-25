"""Categorical encoding + feature renaming ops."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tabprep.ops._registry import op


@op("encode_categoricals")
def encode_categoricals(df: pd.DataFrame, *, label_col: str,
                        max_cardinality: int = 50,
                        method: str = "onehot") -> pd.DataFrame:
    """One-hot encode low-cardinality string columns; drop high-cardinality
    string columns; convert mostly-numeric strings to numeric.

    A column is "mostly numeric" if >90% of its values parse as numbers
    after replacing the literal `"-"` with NaN (a common IDS sentinel).
    """
    if method != "onehot":
        raise ValueError(f"unsupported encode method: {method!r}")

    encoded = df.copy()
    to_onehot: list[str] = []
    to_drop: list[str] = []

    for c in encoded.columns:
        if c == label_col:
            continue
        if encoded[c].dtype != object:
            continue

        numeric = pd.to_numeric(encoded[c].replace("-", np.nan), errors="coerce")
        numeric_frac = numeric.notna().mean()
        if numeric_frac > 0.9:
            encoded[c] = numeric
            continue

        nuniq = encoded[c].nunique(dropna=True)
        if nuniq <= 1:
            to_drop.append(c)
        elif nuniq <= int(max_cardinality):
            to_onehot.append(c)
        else:
            to_drop.append(c)

    if to_onehot:
        # Lower-case + strip for stable category names across machines.
        for c in to_onehot:
            encoded[c] = encoded[c].astype(str).str.strip().str.lower()
        # `pd.get_dummies` uses sorted unique categories — deterministic.
        encoded = pd.get_dummies(encoded, columns=sorted(to_onehot),
                                 prefix=sorted(to_onehot), dtype=np.int8)
    if to_drop:
        encoded = encoded.drop(columns=to_drop)

    return encoded


@op("rename_features_f0fN")
def rename_features_f0fN(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Rename non-label columns to f0, f1, ..., f(N-1) preserving source order.

    Useful for OpenML-style tabular datasets where column names like
    'V1, V2, ...' or 'A1, A2, ...' should be normalised to a consistent
    'f0, f1, ...' convention.
    """
    feat_cols = [c for c in df.columns if c != label_col]
    new_names = {c: f"f{i}" for i, c in enumerate(feat_cols)}
    return df.rename(columns=new_names)
