"""Bot-IoT loader: concat the per-attack-family CSVs.

The Bot-IoT distribution ships several CSVs partitioned by attack
family (DDoS, DoS, OS-fingerprint, Service, Theft, Recon, Normal).
The "10-best-features" subset is a single CSV; the full distribution
is ~74 CSVs. Both layouts are handled by the same recursive
`*.csv` walk + concat.

Each row carries:
  category   — coarse class (DDoS / DoS / Reconnaissance / Theft / Normal)
  subcategory — fine class (HTTP, TCP, UDP, OS_Fingerprint, …)
  attack     — binary label (1 = attack, 0 = benign)

Profile authors typically use `category` as the multi-class target;
`attack` is appropriate for binary tasks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


@loader("bot_iot")
class BotIoTLoader(BaseLoader):
    """Reader for Bot-IoT per-attack-family CSVs.

    Profile usage:
      loader: bot_iot
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
                f"bot_iot loader: no files matching {pattern!r} under {raw_dir}"
            )

        parts: list[pd.DataFrame] = []
        for f in files:
            df = self.read_csv_with_encoding_fallback(f)
            df = df.rename(columns={c: c.strip() for c in df.columns})
            parts.append(df)

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
