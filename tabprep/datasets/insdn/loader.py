"""InSDN loader: concat the three InSDN CSVs (normal + metasploit + OVS).

InSDN's distribution is three CSVs:
  Normal_data.csv     — benign SDN traffic
  metasploitable-2.csv — exploit-based attacks against the data plane
  OVS.csv             — controller / control-plane attacks

Each row carries an upstream `Label` column with attack family. We
concatenate, schema-tolerant, and let the standard pipeline handle
the rest.

`loader_options` supports the same RAM-bounding knobs as the CIC
loaders (`max_rows_per_file`, `sample_mode`, `sample_seed`,
`memory_budget_gb`). InSDN's CSVs are individually small (the entire
distribution fits in <1 GB) so the caps are usually unnecessary, but
they're available for hosts running under tight memory budgets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.core.memguard import MemoryGuard, resolve_budget_bytes
from tabprep.datasets._base import BaseLoader, loader


@loader("insdn")
class InSDNLoader(BaseLoader):
    """Reader for InSDN per-source CSVs.

    Profile usage:
      loader: insdn
      loader_options:
        glob: "*.csv"                # default
        max_rows_per_file: 200000    # optional hard cap per CSV (bounds RAM)
        sample_mode: "head"          # "head" (default) or "reservoir"
        sample_seed: 42
        memory_budget_gb: 8          # optional RSS budget; raises if exceeded
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
        memory_budget_gb: float | None = None,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        pattern = glob or self.DEFAULT_GLOB
        files = self.recursive_glob(Path(raw_dir), (pattern,))
        if not files:
            raise FileNotFoundError(
                f"insdn loader: no files matching {pattern!r} under {raw_dir}"
            )

        guard = MemoryGuard(
            budget_bytes=resolve_budget_bytes(memory_budget_gb),
            label="insdn",
        )
        parts: list[pd.DataFrame] = []
        for f in files:
            if max_rows_per_file is not None:
                df = self.read_csv_with_row_cap(
                    f,
                    max_rows=int(max_rows_per_file),
                    mode=sample_mode,
                    seed=int(sample_seed),
                )
            else:
                df = self.read_csv_with_encoding_fallback(f)
            df = df.rename(columns={c: c.strip() for c in df.columns})
            parts.append(df)
            guard.check(detail=f"after {f.name} ({len(parts)}/{len(files)})")

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
