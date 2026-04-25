"""Source loader: concatenate every CSV under a directory tree.

Used by IDS datasets that ship as multiple CSV files (e.g. CICIDS-2018's
daily files, CIC-IoT-2023's per-device files, UNSW-NB15's split files,
CIC-DDoS-2019's nested CSVs/01-12 + CSVs/03-11 directories).

The label column is expected to live inside the CSVs themselves; if it
needs to be derived from the filename, use `nbaiot_dir` instead.

## What this source does (as of v0.4.x)

- **Recursive search** under `cached_at` for any file with a `.csv`
  extension (case-insensitive). Sub-directories are walked
  automatically; we sort the result by full path so the read order is
  deterministic regardless of OS.
- **Encoding fallback**. The `spec.url` field is reused as a free
  metadata slot:
    - empty / unset                → try `utf-8` then `latin-1`
                                     then `cp1252` per file
    - `"utf-8"` / `"latin-1"` /
      `"cp1252"` / etc.            → use that codec exactly
- **Schema-tolerant concat**. Different sub-directories of the same
  source often have slightly different column sets (e.g. CIC-IoMT-2024
  has Bluetooth-only and WiFi-only columns). `pd.concat` aligns on
  column names and fills missing with NaN; the pipeline's
  `drop_high_nan_columns` op then removes the per-tree extras.

The recursive + encoding-tolerant design lets a maintainer write a
profile *before* downloading the raw data — the source will adapt to
nested directory layouts and mixed-encoding files without further
changes to the profile YAML.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

# Default encoding ladder, tried in order when no specific encoding is
# pinned in the profile. Most modern IDS exports are utf-8; CICFlowMeter
# v3 (CSE-CIC-IDS-2018, CIC-DDoS-2019) used Windows codepage 1252;
# UNSW-NB15 v1 uses latin-1.
_DEFAULT_ENCODINGS: tuple[str, ...] = ("utf-8", "latin-1", "cp1252")


def _resolve_encodings(spec_url: str | None) -> tuple[str, ...]:
    if not spec_url:
        return _DEFAULT_ENCODINGS
    pinned = spec_url.strip().lower()
    if pinned in ("latin1", "latin-1"):
        return ("latin-1",)
    return (pinned,)


def _read_with_encodings(path: Path, encodings: tuple[str, ...]) -> pd.DataFrame:
    """Try each encoding until one succeeds, else raise the last error."""
    last_exc: Exception | None = None
    for enc in encodings:
        try:
            return pd.read_csv(path, low_memory=False, encoding=enc)
        except UnicodeDecodeError as exc:
            last_exc = exc
            continue
    raise RuntimeError(
        f"concat_csvs: could not decode {path} with encodings={encodings}: {last_exc}"
    )


@source("concat_csvs")
def load_concat_csvs(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    if not spec.cached_at:
        raise ValueError("concat_csvs source: profile.source.cached_at is required")
    base = Path(spec.cached_at).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    if not base.is_dir():
        raise FileNotFoundError(f"concat_csvs: directory not found: {base}")

    # Recursive, case-insensitive `.csv` discovery. Sorting by full path
    # gives a deterministic read order regardless of the underlying file-
    # system or OS (HFS+ vs APFS vs ext4 differ on case-folded glob).
    files = sorted(
        p for p in base.rglob("*")
        if p.is_file() and p.suffix.lower() == ".csv"
    )
    if not files:
        raise FileNotFoundError(f"concat_csvs: no CSV files under {base}")

    encodings = _resolve_encodings(spec.url)

    parts: list[pd.DataFrame] = []
    for f in files:
        try:
            d = _read_with_encodings(f, encodings)
        except Exception as exc:                                      # noqa: BLE001
            raise RuntimeError(f"concat_csvs: failed to read {f.name}: {exc}") from exc
        parts.append(d)

    # `pd.concat` aligns columns by name; missing columns become NaN, which
    # the pipeline's drop_high_nan_columns / fill_nan ops handle later.
    df = pd.concat(parts, ignore_index=True)
    return df, label
