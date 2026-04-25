"""NSL-KDD loader: parses KDDTrain+.txt as the canonical training source.

The KDD-99 / NSL-KDD distribution is a CSV-without-header — the schema
is documented at the UNB landing page. 41 features + 2 trailing
columns (`label`, `difficulty`).

We concatenate `KDDTrain+.txt` and `KDDTest+.txt` so a single profile
yields one canonical (train,cal,test) split via the framework's
stratified splitter, rather than the upstream's hand-curated split
(which has its own well-known biases — Test set contains attack
families absent from Train, by design, to test generalisation).

Profile authors who want the upstream's official train/test split
can override `loader_options.use_files` to `["KDDTrain+.txt"]` only,
then assemble their own held-out set.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


# Field names per http://kdd.ics.uci.edu/databases/kddcup99/kddcup.names
_NSL_KDD_COLUMNS: tuple[str, ...] = (
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted",
    "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login",
    "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate", "dst_host_srv_serror_rate",
    "dst_host_rerror_rate", "dst_host_srv_rerror_rate",
    # Trailing label + difficulty:
    "label", "difficulty",
)


@loader("nsl_kdd")
class NSLKDDLoader(BaseLoader):
    """Reader for NSL-KDD `KDDTrain+.txt` / `KDDTest+.txt` files.

    Profile usage:
      loader: nsl_kdd
      loader_options:
        use_files: ["KDDTrain+.txt", "KDDTest+.txt"]   # default
        drop_difficulty: true                          # drop the trailing
                                                       # `difficulty` column
                                                       # (NSL-KDD-specific, not
                                                       # a model feature)
    """

    DEFAULT_USE_FILES: tuple[str, ...] = ("KDDTrain+.txt", "KDDTest+.txt")

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        use_files: list[str] | None = None,
        drop_difficulty: bool = True,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        files_to_use = tuple(use_files or self.DEFAULT_USE_FILES)
        # Find each file (recursive — the ZIP may extract under a subdir).
        parts: list[pd.DataFrame] = []
        raw_dir = Path(raw_dir)
        for fname in files_to_use:
            matches = self.recursive_glob(raw_dir, (fname,))
            if not matches:
                raise FileNotFoundError(
                    f"nsl_kdd loader: {fname!r} not found under {raw_dir}"
                )
            for path in matches:
                df = self.read_csv_with_encoding_fallback(
                    path,
                    header=None,
                    names=list(_NSL_KDD_COLUMNS),
                )
                parts.append(df)

        df = pd.concat(parts, ignore_index=True)
        if drop_difficulty and "difficulty" in df.columns:
            df = df.drop(columns=["difficulty"])
        return df, label_col
