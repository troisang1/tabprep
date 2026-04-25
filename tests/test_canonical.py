"""Unit tests for the canonical CSV writer (`tabprep/core/canonical.py`).

The writer's contract is byte-for-byte determinism — same dataframe +
same parameters → same SHA-256 across machines and Python versions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tabprep.core.canonical import (
    _format_value,
    _row_stable_hash,
    write_canonical_csv,
)
from tabprep.core.hashing import sha256_of_file


# ---------------------------------------------------------------------------
# _format_value — per-cell rendering rules
# ---------------------------------------------------------------------------

def test_format_value_none_and_nan_become_empty():
    assert _format_value(None, precision=6) == ""
    assert _format_value(float("nan"), precision=6) == ""
    assert _format_value(np.nan, precision=6) == ""


def test_format_value_bool_renders_as_zero_or_one():
    assert _format_value(True, precision=6) == "1"
    assert _format_value(False, precision=6) == "0"
    assert _format_value(np.bool_(True), precision=6) == "1"


def test_format_value_integers_have_no_decimals():
    assert _format_value(42, precision=6) == "42"
    assert _format_value(np.int64(7), precision=6) == "7"
    # Negative ints work too.
    assert _format_value(-3, precision=6) == "-3"


def test_format_value_floats_use_fixed_precision():
    assert _format_value(1.5, precision=2) == "1.50"
    assert _format_value(1.5, precision=6) == "1.500000"
    # Avoids scientific notation even for small values.
    assert _format_value(0.0000001, precision=6) == "0.000000"
    # Repeating fractions are truncated, not rounded scientifically.
    assert _format_value(1.0 / 3.0, precision=4) == "0.3333"


def test_format_value_inf_renders_explicitly():
    assert _format_value(float("inf"), precision=6) == "inf"
    assert _format_value(-float("inf"), precision=6) == "-inf"


def test_format_value_strings_minimal_quote():
    """RFC4180-style minimal quoting: only quote when the cell contains
    `,`, `\\n`, or `"`. Plain strings are emitted as-is."""
    assert _format_value("hello", precision=6) == "hello"
    assert _format_value("a,b", precision=6) == '"a,b"'
    assert _format_value('he said "hi"', precision=6) == '"he said ""hi"""'
    assert _format_value("line1\nline2", precision=6) == '"line1\nline2"'


# ---------------------------------------------------------------------------
# _row_stable_hash — used for deterministic row sort
# ---------------------------------------------------------------------------

def test_row_stable_hash_is_deterministic():
    row = pd.Series([1.0, "x", True])
    h1 = _row_stable_hash(row)
    h2 = _row_stable_hash(row)
    assert h1 == h2


def test_row_stable_hash_differs_across_rows():
    a = pd.Series([1.0, "x"])
    b = pd.Series([2.0, "x"])
    assert _row_stable_hash(a) != _row_stable_hash(b)


# ---------------------------------------------------------------------------
# write_canonical_csv — full file integration
# ---------------------------------------------------------------------------

def test_write_canonical_csv_columns_alphabetical(tmp_path):
    df = pd.DataFrame({"b": [1], "c": [2], "a": [3]})
    out = write_canonical_csv(df, tmp_path / "out.csv")
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header == "a,b,c"


def test_write_canonical_csv_columns_source_order(tmp_path):
    df = pd.DataFrame({"z": [1], "a": [2], "m": [3]})
    out = write_canonical_csv(
        df, tmp_path / "out.csv", column_sort="source_order",
    )
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header == "z,a,m"


def test_write_canonical_csv_byte_stable_across_calls(tmp_path):
    """Same df + same params → same bytes."""
    df = pd.DataFrame({
        "f0": [1.0, 2.0, 3.0],
        "f1": [True, False, True],
        "label": ["a", "b", "a"],
    })
    a = write_canonical_csv(df, tmp_path / "a.csv", precision=4, row_shuffle_seed=7)
    b = write_canonical_csv(df, tmp_path / "b.csv", precision=4, row_shuffle_seed=7)
    assert sha256_of_file(a) == sha256_of_file(b)


def test_write_canonical_csv_different_seed_changes_row_order(tmp_path):
    df = pd.DataFrame({
        "x":     list(range(20)),
        "label": ["a", "b"] * 10,
    })
    a = write_canonical_csv(df, tmp_path / "a.csv", row_shuffle_seed=1)
    b = write_canonical_csv(df, tmp_path / "b.csv", row_shuffle_seed=2)
    assert sha256_of_file(a) != sha256_of_file(b)


def test_write_canonical_csv_renders_nan_as_empty(tmp_path):
    df = pd.DataFrame({"x": [1.0, np.nan, 2.0]})
    out = write_canonical_csv(df, tmp_path / "out.csv")
    rows = out.read_text(encoding="utf-8").splitlines()
    # Header + 3 data rows; the NaN row renders as just "" (no token).
    assert rows[0] == "x"
    assert sorted(rows[1:]) == ["", "1.000000", "2.000000"]
    # No literal "nan" or "NaN" token in the file.
    assert "nan" not in out.read_text(encoding="utf-8").lower()


def test_write_canonical_csv_quotes_strings_with_commas(tmp_path):
    df = pd.DataFrame({"text": ["plain", "has,comma"]})
    out = write_canonical_csv(df, tmp_path / "out.csv")
    content = out.read_text(encoding="utf-8")
    assert '"has,comma"' in content
    assert "plain" in content


def test_write_canonical_csv_uses_unix_line_terminator(tmp_path):
    """The writer always uses `\\n`, never `\\r\\n`, regardless of OS
    `os.linesep`. Verified by reading bytes."""
    df = pd.DataFrame({"a": [1, 2]})
    out = write_canonical_csv(df, tmp_path / "out.csv")
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == 3       # header + 2 rows


def test_write_canonical_csv_creates_parent_dir(tmp_path):
    df = pd.DataFrame({"a": [1]})
    nested = tmp_path / "nest" / "ed" / "out.csv"
    out = write_canonical_csv(df, nested)
    assert out.is_file()
