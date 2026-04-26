"""CIC-APT-IIoT-2024 loader: concat the per-stage flow CSVs.

The dataset ships as several CSVs partitioned by APT stage
(`reconnaissance.csv`, `weaponisation.csv`, `delivery.csv`,
`exploitation.csv`, `installation.csv`, `command_control.csv`,
`actions.csv`). The framework concatenates them, schema-tolerantly,
into one labelled flow table.

Mirrors the CIC family pattern (cf. `cicids2018`, `ciciot2023`):
recursive `*.csv` walk, encoding fallback, label derived from the
upstream `Label` column with whitespace stripped.

`loader_options` supports two RAM-bounding knobs:
  * ``max_rows_per_file``: hard cap on rows pulled from each CSV;
    use this on large mirror distributions where the un-capped
    concat would exceed RAM. Combine with ``sample_mode`` =
    ``"reservoir"`` for an unbiased sample, or leave at ``"head"``
    (default) for a deterministic head-N.
  * ``memory_budget_gb``: abort the loader (raising
    `RAMBudgetExceeded`) if RSS crosses this many GiB. When unset,
    falls back to 80% of detected total RAM as a safety net.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.core.memguard import MemoryGuard, resolve_budget_bytes
from tabprep.datasets._base import BaseLoader, loader


@loader("cic_apt_iiot")
class CICAPTIIoTLoader(BaseLoader):
    """Reader for CIC-APT-IIoT-2024 per-stage CSVs.

    Profile usage:
      loader: cic_apt_iiot
      loader_options:
        glob: "*.csv"                   # default; override only if the upstream layout changes
        max_rows_per_file: 250000       # optional hard cap per CSV (bounds RAM)
        sample_mode: "head"             # "head" (default) or "reservoir"
        sample_seed: 42
        memory_budget_gb: 12            # optional RSS budget; raises if exceeded
    """

    DEFAULT_GLOB: str = "*.csv"

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        glob: str | None = None,
        max_rows_per_file: int | None = None,
        sample_mode: str = "head",
        sample_seed: int = 42,
        sample_label_col: str | None = None,
        memory_budget_gb: float | None = None,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        pattern = glob or self.DEFAULT_GLOB
        files = self.recursive_glob(Path(raw_dir), (pattern,))
        if not files:
            raise FileNotFoundError(
                f"cic_apt_iiot loader: no files matching {pattern!r} under {raw_dir}"
            )

        guard = MemoryGuard(
            budget_bytes=resolve_budget_bytes(memory_budget_gb),
            label="cic_apt_iiot",
        )
        parts: list[pd.DataFrame] = []
        for f in files:
            if max_rows_per_file is not None:
                row_cap_kwargs: dict[str, Any] = {
                    "max_rows": int(max_rows_per_file),
                    "mode": sample_mode,
                    "seed": int(sample_seed),
                }
                if sample_mode == "stratified_by_label":
                    # Default to the rename target name (the Kaggle mirror
                    # exposes a lowercase `label` column at the source).
                    row_cap_kwargs["label_column"] = sample_label_col or label_col
                df = self.read_csv_with_row_cap(f, **row_cap_kwargs)
            else:
                df = self.read_csv_with_encoding_fallback(f)
            # CIC CSVs commonly export columns with leading whitespace
            # (' Label', ' Flow ID'). Strip once at the loader so the
            # rest of the pipeline sees clean names.
            df = df.rename(columns={c: c.strip() for c in df.columns})
            parts.append(df)
            guard.check(detail=f"after {f.name} ({len(parts)}/{len(files)})")

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
