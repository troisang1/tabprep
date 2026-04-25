"""InSDN loader: concat the three InSDN CSVs (normal + metasploit + OVS).

InSDN's distribution is three CSVs:
  Normal_data.csv     — benign SDN traffic
  metasploitable-2.csv — exploit-based attacks against the data plane
  OVS.csv             — controller / control-plane attacks

Each row carries an upstream `Label` column with attack family. We
concatenate, schema-tolerant, and let the standard pipeline handle
the rest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


@loader("insdn")
class InSDNLoader(BaseLoader):
    """Reader for InSDN per-source CSVs.

    Profile usage:
      loader: insdn
      loader_options:
        glob: "*.csv"          # default
    """

    DEFAULT_GLOB: str = "*.csv"

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        glob: str | None = None,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        pattern = glob or self.DEFAULT_GLOB
        files = self.recursive_glob(Path(raw_dir), (pattern,))
        if not files:
            raise FileNotFoundError(
                f"insdn loader: no files matching {pattern!r} under {raw_dir}"
            )

        parts: list[pd.DataFrame] = []
        for f in files:
            df = self.read_csv_with_encoding_fallback(f)
            df = df.rename(columns={c: c.strip() for c in df.columns})
            parts.append(df)

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
