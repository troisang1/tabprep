"""CIC-APT-IIoT-2024 loader: concat the per-stage flow CSVs.

The dataset ships as several CSVs partitioned by APT stage
(`reconnaissance.csv`, `weaponisation.csv`, `delivery.csv`,
`exploitation.csv`, `installation.csv`, `command_control.csv`,
`actions.csv`). The framework concatenates them, schema-tolerantly,
into one labelled flow table.

Mirrors the CIC family pattern (cf. `cicids2018`, `ciciot2023`):
recursive `*.csv` walk, encoding fallback, label derived from the
upstream `Label` column with whitespace stripped.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


@loader("cic_apt_iiot")
class CICAPTIIoTLoader(BaseLoader):
    """Reader for CIC-APT-IIoT-2024 per-stage CSVs.

    Profile usage:
      loader: cic_apt_iiot
      loader_options:
        glob: "*.csv"          # default; override only if the upstream layout changes
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
                f"cic_apt_iiot loader: no files matching {pattern!r} under {raw_dir}"
            )

        parts: list[pd.DataFrame] = []
        for f in files:
            df = self.read_csv_with_encoding_fallback(f)
            # CIC CSVs commonly export columns with leading whitespace
            # (' Label', ' Flow ID'). Strip once at the loader so the
            # rest of the pipeline sees clean names.
            df = df.rename(columns={c: c.strip() for c in df.columns})
            parts.append(df)

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
