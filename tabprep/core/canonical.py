"""Canonical CSV writer.

Deterministic byte-for-byte output across Python versions / OSes /
machines. Achieved by:

  * Sort columns alphabetically (configurable to source-order).
  * Sort rows by a stable per-row hash, then optionally shuffle with a
    fixed seed (so the order is reproducible but not identity-leaking).
  * Float values are rendered with a fixed decimal precision via a
    formatter, never through `repr` or platform-dependent `%g`.
  * Use a fixed line terminator (`\\n`), no platform `\\r\\n`.
  * Integers are written as integers (no `.0` suffix).
  * Booleans render as `0` / `1`.

Pandas `to_csv` is fast but not deterministic across versions for floats.
We use a manual writer for the value formatting, while still leveraging
pandas for the in-memory dataframe.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def _row_stable_hash(row: pd.Series) -> int:
    """Stable hash of a row's repr — used for deterministic ordering."""
    h = hashlib.sha256(repr(tuple(row.values)).encode("utf-8")).digest()
    # Take the first 8 bytes as a signed-ish int64; we only need a stable key.
    return int.from_bytes(h[:8], "big", signed=False)


def _format_value(v, precision: int) -> str:
    """Deterministic string repr for one cell."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "1" if bool(v) else "0"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        f = float(v)
        if np.isinf(f):
            return "inf" if f > 0 else "-inf"
        # Fixed precision; avoid scientific notation for stability.
        return f"{f:.{precision}f}"
    s = str(v)
    # Quote strings that contain a comma, newline, or double-quote
    # (RFC4180-style minimal quoting). Use double-quote escaping.
    if any(ch in s for ch in (",", "\n", '"')):
        s = s.replace('"', '""')
        return f'"{s}"'
    return s


def write_canonical_csv(
    df: pd.DataFrame,
    out_path: str | Path,
    *,
    precision: int = 6,
    column_sort: str = "alphabetical",
    row_shuffle_seed: int = 42,
) -> Path:
    """Write `df` to `out_path` in canonical form (see module docstring)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if column_sort == "alphabetical":
        cols = sorted(df.columns.tolist())
    elif column_sort == "source_order":
        cols = list(df.columns)
    else:
        raise ValueError(f"unknown column_sort {column_sort!r}")

    work = df.loc[:, cols].copy()

    # Stable sort by per-row hash, then a deterministic shuffle by seed.
    keys = work.apply(_row_stable_hash, axis=1).to_numpy(dtype=np.uint64)
    order = np.argsort(keys, kind="stable")
    work = work.iloc[order].reset_index(drop=True)
    if row_shuffle_seed is not None:
        rng = np.random.default_rng(row_shuffle_seed)
        perm = rng.permutation(len(work))
        work = work.iloc[perm].reset_index(drop=True)

    # Manual write with fixed-precision float formatting.
    with out.open("w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(cols) + "\n")
        for _, row in work.iterrows():
            fh.write(",".join(_format_value(v, precision) for v in row.values) + "\n")

    return out
