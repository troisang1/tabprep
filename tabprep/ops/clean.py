"""Cleaning ops: drop columns, NaN/Inf handling, IP-leakage removal."""
from __future__ import annotations

import numpy as np
import pandas as pd

from tabprep.ops._registry import op


@op("drop_columns")
def drop_columns(df: pd.DataFrame, *, label_col: str,
                 columns: list[str]) -> pd.DataFrame:
    """Drop the named columns, ignoring any that are absent."""
    return df.drop(columns=[c for c in (columns or []) if c in df.columns], errors="ignore")


@op("drop_constant_columns")
def drop_constant_columns(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Drop columns with a single unique non-NaN value (excluding the label)."""
    drop = []
    for c in df.columns:
        if c == label_col:
            continue
        if df[c].nunique(dropna=True) <= 1:
            drop.append(c)
    return df.drop(columns=drop) if drop else df


@op("drop_ip_columns")
def drop_ip_columns(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Drop common IP-address columns (identity leakage in network IDS data)."""
    patterns = (
        "src_ip", "dst_ip", "ip.src_host", "ip.dst_host",
        "arp.src.proto_ipv4", "arp.dst.proto_ipv4",
        "srcip", "dstip", "src_addr", "dst_addr",
    )
    drop = [c for c in df.columns if c != label_col
            and any(p in c.lower() for p in patterns)]
    return df.drop(columns=drop) if drop else df


@op("drop_high_nan_columns")
def drop_high_nan_columns(df: pd.DataFrame, *, label_col: str,
                          threshold: float = 0.8) -> pd.DataFrame:
    """Drop columns where the NaN fraction exceeds `threshold`."""
    feat = df.drop(columns=[label_col], errors="ignore")
    na_frac = feat.isna().mean()
    drop = na_frac[na_frac > float(threshold)].index.tolist()
    return df.drop(columns=drop) if drop else df


@op("replace_inf")
def replace_inf(df: pd.DataFrame, *, label_col: str,
                value: float | None = None) -> pd.DataFrame:
    """Replace ±inf with NaN (default) or with a numeric `value`."""
    if value is None:
        return df.replace([np.inf, -np.inf], np.nan)
    return df.replace([np.inf, -np.inf], float(value))


@op("fill_nan")
def fill_nan(df: pd.DataFrame, *, label_col: str,
             value: float = 0.0) -> pd.DataFrame:
    """Fill NaN with a numeric constant (typical: 0)."""
    return df.fillna(float(value))


@op("coerce_numeric")
def coerce_numeric(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Coerce non-label string columns to numeric (NaN on failure)."""
    out = df.copy()
    for c in out.columns:
        if c == label_col:
            continue
        if out[c].dtype == object:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out
