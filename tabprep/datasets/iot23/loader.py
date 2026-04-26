"""IoT-23 loader: parses Stratosphere Lab `conn.log.labeled` Zeek files.

IoT-23 ships every capture as a Zeek connection log labelled with two
trailing columns (`label`, `detailed-label`). The catch:

  * The first 21 fields use the standard Zeek tab separator.
  * The trailing two label columns are appended **space-separated**
    inside the last tab-token of the `#fields` header (and every data
    row). This is a known Stratosphere quirk — the labelling tool
    that produced the dataset glued the labels onto each row with
    spaces rather than tabs.

A naive tab-only reader sees 22 fields where there should be 23, and
crams `tunnel_parents`, `label`, and `detailed-label` into a single
string column. We work around this by:

  1. Flattening any whitespace inside each tab-token of the `#fields`
     header so the column-name list is correct.
  2. Reading data rows with `sep=r"\\s+"` (whitespace tokenisation),
     which handles both standard tab-only Zeek output and IoT-23's
     mixed-tab-space layout in a single pass.

Per-file row capping is supported via `loader_options.per_file_cap`,
because some IoT-23 captures (e.g. CTU-IoT-Malware-Capture-39-1) have
>100M flows and would OOM a single in-memory concat. The cap takes the
first N rows of each capture (head-N — deterministic).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.core.memguard import MemoryGuard, resolve_budget_bytes
from tabprep.datasets._base import BaseLoader, loader


def _parse_zeek_fields_header(path: Path) -> list[str]:
    """Read the `#fields` line and return the column names.

    Handles IoT-23's quirk where the tail token contains whitespace-
    separated names. Returns the flat list of field names.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#fields"):
                tokens = line.rstrip("\n").split("\t")[1:]
                fields: list[str] = []
                for tok in tokens:
                    fields.extend(tok.split())
                return fields
    raise RuntimeError(f"iot23 loader: no #fields header in {path}")


@loader("iot23")
class IoT23Loader(BaseLoader):
    """Reader for the IoT-23 lite tarball's `*.labeled` files.

    Profile usage:
      loader: iot23
      loader_options:
        per_file_cap: 50000     # head-N per capture; default = no cap
        glob:        "*.labeled"  # rare override; default below
    """

    DEFAULT_GLOB: str = "*.labeled"

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        glob: str | None = None,
        per_file_cap: int | None = None,
        memory_budget_gb: float | None = None,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        pattern = glob or self.DEFAULT_GLOB
        files = self.recursive_glob(Path(raw_dir), (pattern,))
        if not files:
            raise FileNotFoundError(
                f"iot23 loader: no files matching {pattern!r} under {raw_dir}"
            )

        guard = MemoryGuard(
            budget_bytes=resolve_budget_bytes(memory_budget_gb),
            label="iot23",
        )
        parts: list[pd.DataFrame] = []
        for f in files:
            fields = _parse_zeek_fields_header(f)
            kwargs: dict[str, Any] = {
                "sep": r"\s+",
                "header": None,
                "names": fields,
                "comment": "#",
                "engine": "python",
                "na_values": ["-", "(empty)"],
            }
            if per_file_cap is not None:
                kwargs["nrows"] = int(per_file_cap)
            df = pd.read_csv(f, **kwargs)
            parts.append(df)
            guard.check(detail=f"after {f.name} ({len(parts)}/{len(files)})")

        df = pd.concat(parts, ignore_index=True)
        return df, label_col
