"""UNSW-NB15 loader: read the four numbered headerless CSVs.

The UNSW-NB15 distribution (Moustafa & Slay, 2015) ships **headerless**
CSVs — every row is data; the column schema lives in a separate
`UNSW-NB15_features.csv` companion file. The generic `concat_csvs`
source can't handle this because it always treats the first row as
the header and so consumes data values as column names. This loader
injects the published 49-column schema before reading.

The schema below matches the v2 feature dictionary
(`NUSW-NB15_features.csv` on the UNSW research portal). Columns 48 +
49 (`attack_cat` + `Label`) are the targets — `attack_cat` is the
multi-class label this profile uses, and the binary `Label` column
gets dropped by the rename step in the framework's pipeline executor.

Loader options:
  * ``max_rows_per_file``: optional hard cap per CSV — bounds RAM on
    the largest file (`UNSW-NB15_2.csv` ≈ 4 GB).
  * ``sample_mode``: ``"head"`` (default, deterministic) or
    ``"reservoir"`` (unbiased, single full pass).
  * ``sample_seed``: int.
  * ``memory_budget_gb``: per-loader RSS ceiling (defaults to 80% of
    detected RAM via the framework's `MemoryGuard`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.core.memguard import MemoryGuard, resolve_budget_bytes
from tabprep.datasets._base import BaseLoader, loader


# Canonical 49-column schema for UNSW-NB15 v2. Column names match the
# published `NUSW-NB15_features.csv` exactly (case included). The two
# ground-truth columns are `attack_cat` (multi-class) and `Label`
# (binary 0/1).
UNSW_NB15_COLUMNS: tuple[str, ...] = (
    "srcip",
    "sport",
    "dstip",
    "dsport",
    "proto",
    "state",
    "dur",
    "sbytes",
    "dbytes",
    "sttl",
    "dttl",
    "sloss",
    "dloss",
    "service",
    "Sload",
    "Dload",
    "Spkts",
    "Dpkts",
    "swin",
    "dwin",
    "stcpb",
    "dtcpb",
    "smeansz",
    "dmeansz",
    "trans_depth",
    "res_bdy_len",
    "Sjit",
    "Djit",
    "Stime",
    "Ltime",
    "Sintpkt",
    "Dintpkt",
    "tcprtt",
    "synack",
    "ackdat",
    "is_sm_ips_ports",
    "ct_state_ttl",
    "ct_flw_http_mthd",
    "is_ftp_login",
    "ct_ftp_cmd",
    "ct_srv_src",
    "ct_srv_dst",
    "ct_dst_ltm",
    "ct_src_ltm",
    "ct_src_dport_ltm",
    "ct_dst_sport_ltm",
    "ct_dst_src_ltm",
    "attack_cat",
    "Label",
)


@loader("unsw_nb15")
class UNSWNB15Loader(BaseLoader):
    """Reader for the four headerless UNSW-NB15 CSVs.

    Profile usage:
      loader: unsw_nb15
      loader_options:
        glob: "UNSW-NB15_*.csv"      # default; restricts to numbered CSVs
                                     # so an accidentally co-located
                                     # GT/features CSV doesn't sneak in.
        max_rows_per_file: 1000000   # optional bound for huge files
        sample_mode: head
        sample_seed: 42
        memory_budget_gb: 16
    """

    DEFAULT_GLOB: str = "UNSW-NB15_*.csv"

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
                f"unsw_nb15 loader: no files matching {pattern!r} under {raw_dir}"
            )

        guard = MemoryGuard(
            budget_bytes=resolve_budget_bytes(memory_budget_gb),
            label="unsw_nb15",
        )
        # `header=None` + `names=` is the required combination — without
        # it pandas treats the first data row as the header. The CSVs
        # have a UTF-8 BOM on file 1; `encoding="utf-8-sig"` strips it.
        # latin-1 fallback covers a handful of non-ASCII bytes that
        # appear in the URL fields of HTTP traffic rows.
        read_kwargs: dict[str, Any] = {
            "header": None,
            "names": list(UNSW_NB15_COLUMNS),
        }
        encodings = ("utf-8-sig", "latin-1", "cp1252")

        parts: list[pd.DataFrame] = []
        for f in files:
            if max_rows_per_file is not None:
                df = self.read_csv_with_row_cap(
                    f,
                    max_rows=int(max_rows_per_file),
                    mode=sample_mode,
                    seed=int(sample_seed),
                    encodings=encodings,
                    **read_kwargs,
                )
            else:
                df = self.read_csv_with_encoding_fallback(
                    f, encodings=encodings, **read_kwargs
                )
            parts.append(df)
            guard.check(detail=f"after {f.name} ({len(parts)}/{len(files)})")

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
