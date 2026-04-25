"""Bot-IoT loader: concat the 4 reduced_data_*.csv files.

The Kaggle `vigneshvenkateswaran/bot-iot-5-data` ZIP extracts to:

    reduced_data_1.csv
    reduced_data_2.csv
    reduced_data_3.csv
    reduced_data_4.csv

Each ~280 MB uncompressed. Schema: 46 columns including `attack`
(binary), `category` (multi-class: DDoS / DoS / Reconnaissance /
Theft / Normal), `subcategory` (fine-grained), and 43 flow features.

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
    """Reader for the Bot-IoT 5%-data Kaggle mirror.

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
