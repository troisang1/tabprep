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
- **RAM-bounded reads**. The `glob` field of `SourceSpec` is overloaded
  to also carry per-file row caps:
    - `"*.csv|max_rows_per_file=200000"`            → head-N per file
    - `"*.csv|max_rows_per_file=200000|sample=reservoir"` → unbiased sample
    - `"*.csv|memory_budget_gb=12"`                 → abort if RSS > 12 GiB
  Multiple options are pipe-separated. Without these caps the loader
  reads every CSV whole, which on the 29 GB CIC-DDoS-2019 distribution
  exhausts a 64 GB host before `pd.concat`. With the cap, memory is
  bounded at `(max_rows_per_file × n_files × row_bytes)`.

The recursive + encoding-tolerant design lets a maintainer write a
profile *before* downloading the raw data — the source will adapt to
nested directory layouts and mixed-encoding files without further
changes to the profile YAML.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.memguard import MemoryGuard, resolve_budget_bytes
from tabprep.core.profile import SourceSpec
from tabprep.datasets._base import BaseLoader
from tabprep.sources._registry import source

# Default encoding ladder, tried in order when no specific encoding is
# pinned in the profile. Most modern IDS exports are utf-8; CICFlowMeter
# v3 (CSE-CIC-IDS-2018, CIC-DDoS-2019) used Windows codepage 1252;
# UNSW-NB15 v1 uses latin-1.
_DEFAULT_ENCODINGS: tuple[str, ...] = ("utf-8", "latin-1", "cp1252")


def _resolve_encodings(spec) -> tuple[str, ...]:
    """Pick an encoding from the SourceSpec.

    Priority:
      1. `spec.encoding` (typed field, preferred for new profiles).
      2. `spec.url` (legacy overload — accepted for backward compat with
         profiles authored before the `encoding` field existed).
      3. Default ladder: utf-8 → latin-1 → cp1252.
    """
    pinned = spec.encoding or spec.url
    if not pinned:
        return _DEFAULT_ENCODINGS
    pinned = pinned.strip().lower()
    if pinned in ("latin1", "latin-1"):
        return ("latin-1",)
    return (pinned,)


def _parse_glob_options(glob: str | None) -> dict[str, str]:
    """Parse the pipe-overloaded glob field into a dict of options.

    `"*.csv|max_rows_per_file=200000|sample=reservoir"` →
    `{"pattern": "*.csv", "max_rows_per_file": "200000", "sample": "reservoir"}`

    Unrecognised keys are kept verbatim — callers ignore what they
    don't use, which lets us extend the vocabulary without breaking
    older profiles. Returns `{"pattern": "*.csv"}` when `glob` is
    None (the default discovery pattern).
    """
    if not glob:
        return {"pattern": "*.csv"}
    parts = [p.strip() for p in glob.split("|") if p.strip()]
    out: dict[str, str] = {"pattern": parts[0] or "*.csv"}
    for token in parts[1:]:
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        # Strip the key but preserve whitespace inside the value: some
        # CIC CSVs ship the label column as ` Label` (leading space)
        # and the profile must be able to specify that verbatim. The
        # numeric/boolean parsers downstream tolerate trailing whitespace.
        out[k.strip()] = v
    return out


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

    opts = _parse_glob_options(spec.glob)
    pattern = opts["pattern"]
    max_rows_per_file = (
        int(opts["max_rows_per_file"]) if "max_rows_per_file" in opts else None
    )
    # sample_mode in {"head", "reservoir", "stratified_by_label"}.
    # `stratified_by_label` does a two-pass class-aware sample inside
    # each file — guarantees no class is silently dropped, at the cost
    # of a second read of the file. For class-mixed CIC distributions
    # this is the right default.
    sample_mode = opts.get("sample", "head")
    sample_seed = int(opts.get("sample_seed", "42"))
    # When sample=stratified_by_label, the column to bin by is taken
    # from `sample_label_col` (defaults to the rename target the
    # pipeline expects). Note: this is the column name AS IT APPEARS
    # IN THE CSV HEADER — for CIC-DDoS-2019 that's " Label" with a
    # leading space; the profile passes the literal string verbatim.
    sample_label_col = opts.get("sample_label_col") or label
    memory_budget_gb = (
        float(opts["memory_budget_gb"]) if "memory_budget_gb" in opts else None
    )

    # Recursive, case-insensitive `.csv` discovery. Sorting by full path
    # gives a deterministic read order regardless of the underlying file-
    # system or OS (HFS+ vs APFS vs ext4 differ on case-folded glob).
    if pattern == "*.csv":
        files = sorted(
            p for p in base.rglob("*")
            if p.is_file() and p.suffix.lower() == ".csv"
        )
    else:
        files = sorted(p for p in base.rglob(pattern) if p.is_file())
    if not files:
        raise FileNotFoundError(f"concat_csvs: no CSV files under {base}")

    encodings = _resolve_encodings(spec)
    guard = MemoryGuard(
        budget_bytes=resolve_budget_bytes(memory_budget_gb),
        label="concat_csvs",
    )

    parts: list[pd.DataFrame] = []
    for f in files:
        try:
            if max_rows_per_file is not None:
                row_cap_kwargs: dict[str, object] = {
                    "max_rows": max_rows_per_file,
                    "mode": sample_mode,
                    "seed": sample_seed,
                    "encodings": encodings,
                }
                if sample_mode == "stratified_by_label":
                    row_cap_kwargs["label_column"] = sample_label_col
                d = BaseLoader.read_csv_with_row_cap(f, **row_cap_kwargs)
            else:
                d = _read_with_encodings(f, encodings)
        except Exception as exc:                                      # noqa: BLE001
            raise RuntimeError(f"concat_csvs: failed to read {f.name}: {exc}") from exc
        parts.append(d)
        guard.check(detail=f"after {f.name} ({len(parts)}/{len(files)})")

    # `pd.concat` aligns columns by name; missing columns become NaN, which
    # the pipeline's drop_high_nan_columns / fill_nan ops handle later.
    df = pd.concat(parts, ignore_index=True)
    return df, label
