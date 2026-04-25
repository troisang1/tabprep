"""Source loader: Zeek (formerly Bro) `conn.log.labeled` files.

Used by IoT-23 (Stratosphere Lab) and other malware captures that ship
labelled Zeek connection logs. Format:

    #separator \\x09
    #set_separator    ,
    #empty_field    (empty)
    #unset_field    -
    #path    conn
    #fields    ts    uid    id.orig_h    id.orig_p    ...    label    detailed-label
    #types     time   string ...
    1545379977.461    Cw7Yh...    192.168.1.198    49259    ...    Malicious   PartOfAHorizontalPortScan
    ...

The `#fields` line gives the column names. All other `#` lines are
metadata. `-` is the missing-value sentinel.

The loader walks the directory recursively and concatenates every file
matching `*.labeled`, so a typical IoT-23 download — 23 capture
sub-directories, each with one `conn.log.labeled` — is handled with a
single profile.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

# Glob pattern for Zeek log files. Override via SourceSpec.url field if
# you need to read a different extension (e.g. some mirrors ship `.log`
# without `.labeled`).
DEFAULT_GLOB = "*.labeled"

# Optional per-file row cap. Some IoT-23 captures contain >100M rows, which
# would OOM a single pandas concat. The cap is encoded in `SourceSpec.url`
# as e.g. "per_file_cap=50000" (combinable with the glob via "|", e.g.
# "*.labeled|per_file_cap=50000"). The cap is applied as a deterministic
# stratified-by-file head sample (we keep the *first* N data rows of each
# file, after the metadata header). Random sampling would compromise
# reproducibility because pandas' chunked reads do not seed predictably.
_CAP_RE = re.compile(r"per_file_cap=(\d+)")


def _read_zeek_header(path: Path) -> list[str]:
    """Extract the column names from a Zeek `#fields` header line.

    Standard Zeek output is tab-separated everywhere. IoT-23's labelled
    captures break that convention by appending two extra columns
    (`label` + `detailed-label`) using ASCII space as the separator —
    so the last raw `\\t`-token of the header / each data row contains
    `tunnel_parents   label   detailed-label`. We detect this by
    splitting any tab-token on whitespace and flattening; downstream
    `read_csv` then uses whitespace tokenisation for the data rows.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#fields"):
                tokens = line.rstrip("\n").split("\t")[1:]
                # Flatten any tokens that contain embedded whitespace.
                fields: list[str] = []
                for tok in tokens:
                    fields.extend(tok.split())
                return fields
    raise RuntimeError(f"zeek_conn_log: no #fields header in {path}")


def _parse_options(opt_str: str | None) -> tuple[str, int | None]:
    """Pull `glob` and `per_file_cap` out of the SourceSpec.url metadata."""
    if not opt_str:
        return DEFAULT_GLOB, None
    pattern = DEFAULT_GLOB
    cap: int | None = None
    for part in opt_str.split("|"):
        part = part.strip()
        if not part:
            continue
        if "*" in part:
            pattern = part
        else:
            m = _CAP_RE.match(part)
            if m:
                cap = int(m.group(1))
    return pattern, cap


@source("zeek_conn_log")
def load_zeek_conn_log(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    if not spec.cached_at:
        raise ValueError("zeek_conn_log: profile.source.cached_at is required")
    base = Path(spec.cached_at).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    if not base.is_dir():
        raise FileNotFoundError(f"zeek_conn_log: directory not found: {base}")

    pattern, per_file_cap = _parse_options(spec.url)
    log_files = sorted(base.rglob(pattern))
    if not log_files:
        raise FileNotFoundError(
            f"zeek_conn_log: no files matching {pattern!r} under {base}"
        )

    parts: list[pd.DataFrame] = []
    for f in log_files:
        fields = _read_zeek_header(f)
        # `sep=r"\s+"` (whitespace) handles both standard tab-only Zeek
        # output and IoT-23's mixed tab+space layout in a single read.
        # Requires engine="python" but is acceptable here — TSV reads
        # are I/O-bound, not CPU-bound.
        kwargs = dict(
            sep=r"\s+",
            header=None,
            names=fields,
            comment="#",
            engine="python",
            na_values=["-", "(empty)"],
        )
        if per_file_cap is not None:
            kwargs["nrows"] = per_file_cap
        df = pd.read_csv(f, **kwargs)
        parts.append(df)

    df = pd.concat(parts, ignore_index=True)
    return df, label
