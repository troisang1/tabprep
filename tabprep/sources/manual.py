"""Source loader: manually downloaded local CSV (no integrity check)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source


@source("manual")
def load_manual(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    if not spec.cached_at:
        raise ValueError("manual source: profile.source.cached_at is required")
    p = Path(spec.cached_at).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.is_file():
        raise FileNotFoundError(f"manual source: file not found: {p}")
    df = pd.read_csv(p, low_memory=False)
    return df, label
