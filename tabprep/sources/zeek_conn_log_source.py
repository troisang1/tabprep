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

from pathlib import Path

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

# Glob pattern for Zeek log files. Override via SourceSpec.url field if
# you need to read a different extension (e.g. some mirrors ship `.log`
# without `.labeled`).
DEFAULT_GLOB = "*.labeled"


def _read_zeek_header(path: Path) -> list[str]:
    """Extract the column names from a Zeek `#fields` header line."""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#fields"):
                # "#fields\tts\tuid\t..."  →  ["ts", "uid", ...]
                return line.rstrip("\n").split("\t")[1:]
    raise RuntimeError(f"zeek_conn_log: no #fields header in {path}")


@source("zeek_conn_log")
def load_zeek_conn_log(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    if not spec.cached_at:
        raise ValueError("zeek_conn_log: profile.source.cached_at is required")
    base = Path(spec.cached_at).expanduser()
    if not base.is_absolute():
        base = Path.cwd() / base
    if not base.is_dir():
        raise FileNotFoundError(f"zeek_conn_log: directory not found: {base}")

    # SourceSpec.url is reused as a free metadata field — set it to a
    # different glob (e.g. "*.log") to override the default.
    pattern = spec.url if (spec.url and "*" in spec.url) else DEFAULT_GLOB
    log_files = sorted(base.rglob(pattern))
    if not log_files:
        raise FileNotFoundError(
            f"zeek_conn_log: no files matching {pattern!r} under {base}"
        )

    parts: list[pd.DataFrame] = []
    for f in log_files:
        fields = _read_zeek_header(f)
        df = pd.read_csv(
            f,
            sep="\t",
            header=None,
            names=fields,
            comment="#",
            low_memory=False,
            na_values=["-", "(empty)"],
        )
        parts.append(df)

    df = pd.concat(parts, ignore_index=True)
    return df, label
