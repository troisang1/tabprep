"""Source loader: concatenate every CSV under a directory.

Used by IDS datasets that ship as multiple CSV files (e.g. CICIDS-2018's
daily files, CIC-IoT-2023's per-device files, UNSW-NB15's split files).

The label column is expected to live inside the CSVs themselves; if it
needs to be derived from the filename, use `nbaiot_dir` instead.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source


@source("concat_csvs")
def load_concat_csvs(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    """`cached_at` is interpreted as a directory under `data/raw/...`.
    All `*.csv` files in it are read and concatenated in lexical filename
    order. `read_csv` uses `low_memory=False` for stability.

    Optional encoding override via `spec.url` field (we reuse it as a free
    metadata slot — formal extension TBD): set to `latin-1` for
    UNSW-NB15-style files. Default is utf-8.
    """
    if not spec.cached_at:
        raise ValueError("concat_csvs source: profile.source.cached_at is required")
    base = Path(spec.cached_at).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    if not base.is_dir():
        raise FileNotFoundError(f"concat_csvs: directory not found: {base}")

    files = sorted(base.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"concat_csvs: no CSVs in {base}")

    encoding = "utf-8"
    # `spec.url` is reused as a free metadata field; if it equals "latin-1"
    # we use that codec. (Formal alternative: extend SourceSpec with an
    # `options: dict` slot — left for v0.4.)
    if spec.url and spec.url.lower() in ("latin-1", "latin1"):
        encoding = "latin-1"

    parts: list[pd.DataFrame] = []
    for f in files:
        try:
            d = pd.read_csv(f, low_memory=False, encoding=encoding)
            parts.append(d)
        except Exception as exc:                                      # noqa: BLE001
            raise RuntimeError(f"concat_csvs: failed to read {f.name}: {exc}") from exc

    df = pd.concat(parts, ignore_index=True)
    return df, label
