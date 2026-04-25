"""Source loader: N-BaIoT directory of `<device>_<attack>.csv` files.

N-BaIoT ships one CSV per (device, attack) combination, with the attack
type encoded in the filename (`1.benign.csv`, `1.gafgyt.combo.csv`, …).
The label is therefore extracted from the filename, NOT from a column.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source


def _label_from_filename(stem: str) -> str:
    name = stem.lower()
    if "benign" in name:
        return "benign"
    parts_name = name.split("_")
    return "_".join(parts_name[-2:]) if len(parts_name) >= 2 else name


@source("nbaiot_dir")
def load_nbaiot_dir(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    if not spec.cached_at:
        raise ValueError("nbaiot_dir: profile.source.cached_at is required")
    base = Path(spec.cached_at).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    if not base.is_dir():
        raise FileNotFoundError(f"nbaiot_dir: directory not found: {base}")

    parts: list[pd.DataFrame] = []
    for f in sorted(base.glob("*.csv")):
        try:
            d = pd.read_csv(f, low_memory=False)
        except Exception:                                              # noqa: BLE001
            continue
        d[label] = _label_from_filename(f.stem)
        parts.append(d)

    if not parts:
        raise FileNotFoundError(f"nbaiot_dir: no readable CSVs in {base}")

    df = pd.concat(parts, ignore_index=True)
    return df, label
