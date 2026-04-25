"""Bot-IoT loader: fetches the OpenML mirror via sklearn.fetch_openml.

Bot-IoT's authoritative distribution is the OpenML mirror (id 42072,
`bot-iot-all-features`) since the original AARNet Cloudstor host was
decommissioned in 2023. This loader uses sklearn's OpenML proxy —
parallel to `OpenMLLoader` but with the dataset name pinned in code
(matches the `BotIoTDownloader.OPENML_NAME` attribute).

The `bot-iot-all-features` mirror is the **10-best-features** subset
(3.6M rows × 10 numeric features). The label column is `category`
(coarse multi-class: DDoS / DoS / Reconnaissance / Theft / Normal).
The fine-grained `subcategory` and binary `attack` columns are also
present in the upstream distribution but not in this OpenML mirror.

`raw_dir` is unused — sklearn caches under `~/scikit_learn_data/`.
The `_complete` marker written by `BotIoTDownloader.download` lets
the framework's idempotency check work consistently.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


@loader("bot_iot")
class BotIoTLoader(BaseLoader):
    """Reader for the Bot-IoT 10-best-features OpenML mirror.

    Profile usage:
      loader: bot_iot
      loader_options:
        openml_name: bot-iot-all-features    # default
        openml_version: 1                    # default
    """

    DEFAULT_NAME: str = "bot-iot-all-features"
    DEFAULT_VERSION: int = 1

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        openml_name: str | None = None,
        openml_version: int | str = DEFAULT_VERSION,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        from sklearn.datasets import fetch_openml

        bunch = fetch_openml(
            openml_name or self.DEFAULT_NAME,
            version=openml_version,
            as_frame=True,
            parser="auto",
        )
        # OpenML returns categorical targets; coerce to string for the label.
        y = bunch.target.astype(str).reset_index(drop=True)
        df = bunch.data.reset_index(drop=True).copy()
        df[label_col] = y.values
        return df, label_col
