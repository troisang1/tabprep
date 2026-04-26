"""Source loader: N-BaIoT directory of per-(device, attack) CSV files.

N-BaIoT ships one CSV per (device, attack) combination, with the
attack family + sub-attack encoded in the filename. The label is
therefore extracted from the filename, NOT from a column.

## Supported file layouts

The original UCI distribution arrives as a ZIP that extracts to one
sub-directory per device, with each device dir containing
`benign_traffic.csv` plus `gafgyt_attacks.rar` / `mirai_attacks.rar`
archives. Those archives need a separate `unrar` step that we don't
ship — extracting them is a manual prerequisite.

The Kaggle mirror `mkashifn/nbaiot-dataset` ships **pre-extracted**:
93 CSVs in a flat layout, named `<device-id>.<family>.<attack>.csv`
(e.g. `1.benign.csv`, `1.gafgyt.combo.csv`, `1.mirai.udpplain.csv`).
The framework's nbaiot profile uses this mirror so no `.rar` step is
needed.

Both layouts are handled transparently by the loader: the search is
recursive (`rglob("*.csv")`), and the label parser accepts either
underscore-separated (`<device>_<attack>.csv`, the legacy convention)
or dot-separated (`<device>.<family>.<attack>.csv`, Kaggle mirror).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.memguard import MemoryGuard, resolve_budget_bytes
from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

# Kaggle mirror also ships a `demonstrate_structure.csv` next to the
# data CSVs — it is a 5-row schema-illustration file with the SAME
# column count as a real per-device file but no actual labelled rows.
# We skip it explicitly so it doesn't pollute the concat.
_SKIP_FILENAMES = {"demonstrate_structure.csv"}


def _label_from_filename(stem: str) -> str:
    """Derive a class label from a (device-stripped) filename stem.

    Two conventions are supported, distinguishable by separator:

      * Kaggle dot-separated (`1.gafgyt.combo` → `gafgyt_combo`,
        `1.benign` → `benign`).
      * UCI underscore-separated (`Danmini_Doorbell_gafgyt_combo`
        → `gafgyt_combo`, `Danmini_Doorbell_benign` → `benign`).

    Falls back to the bare lower-cased stem when the filename matches
    neither pattern.
    """
    name = stem.lower()
    if "benign" in name:
        return "benign"
    if "." in name:
        # Kaggle layout: `<device>.<family>.<sub>` — drop the device id,
        # join the rest with underscores so the label is filesystem-safe.
        parts = name.split(".")
        if len(parts) >= 3:
            return "_".join(parts[1:])
        if len(parts) == 2:
            return parts[1]
        return name
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

    # Recursive walk — handles both the flat Kaggle layout (CSVs at
    # `base/`) and the per-device UCI layout (CSVs at `base/<device>/`).
    files = sorted(
        f for f in base.rglob("*.csv")
        if f.is_file() and f.name.lower() not in _SKIP_FILENAMES
    )
    if not files:
        raise FileNotFoundError(
            f"nbaiot_dir: no readable CSVs found anywhere under {base}. "
            f"If the upstream distribution shipped `.rar` archives "
            f"(UCI layout), extract them first or switch to the Kaggle "
            f"mirror `mkashifn/nbaiot-dataset` which ships the CSVs "
            f"pre-extracted."
        )

    guard = MemoryGuard(
        budget_bytes=resolve_budget_bytes(None),
        label="nbaiot_dir",
    )
    parts: list[pd.DataFrame] = []
    for f in files:
        try:
            d = pd.read_csv(f, low_memory=False)
        except Exception:                                              # noqa: BLE001
            continue
        d[label] = _label_from_filename(f.stem)
        parts.append(d)
        guard.check(detail=f"after {f.name} ({len(parts)}/{len(files)})")

    if not parts:
        raise FileNotFoundError(f"nbaiot_dir: no readable CSVs in {base}")

    df = pd.concat(parts, ignore_index=True)
    return df, label
