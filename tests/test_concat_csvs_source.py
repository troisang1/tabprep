"""Tests for the concat_csvs source loader."""
from __future__ import annotations

from pathlib import Path


from tabprep.core.profile import SourceSpec
from tabprep.sources.concat_csvs_source import load_concat_csvs


def _write_csv(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)


def test_recursive_discovery(tmp_path):
    # Three CSVs at three different depths — should all be picked up.
    _write_csv(tmp_path / "a.csv", "x,label\n1,A\n")
    _write_csv(tmp_path / "sub1" / "b.csv", "x,label\n2,B\n")
    _write_csv(tmp_path / "sub1" / "sub2" / "c.csv", "x,label\n3,C\n")
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path))
    df, _ = load_concat_csvs(spec, label="label")
    assert sorted(df["label"].tolist()) == ["A", "B", "C"]
    assert sorted(df["x"].tolist()) == [1, 2, 3]


def test_case_insensitive_csv_extension(tmp_path):
    # Mixed-case file extensions — should all match.
    _write_csv(tmp_path / "lower.csv", "x,label\n1,A\n")
    _write_csv(tmp_path / "upper.CSV", "x,label\n2,B\n")
    _write_csv(tmp_path / "mixed.Csv", "x,label\n3,C\n")
    # Also write a non-CSV that should be ignored.
    (tmp_path / "readme.txt").write_text("not data", encoding="utf-8")
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path))
    df, _ = load_concat_csvs(spec, label="label")
    assert len(df) == 3


def test_encoding_fallback_to_latin1(tmp_path):
    # File with a latin-1-only byte (0xa0 = non-breaking space). utf-8
    # will choke; latin-1 will succeed. With no encoding pinned the
    # loader should fall through to latin-1 automatically.
    p = tmp_path / "latin.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x,label\n1,caf\xe9\n")
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path))
    df, _ = load_concat_csvs(spec, label="label")
    assert df.loc[0, "label"] == "café"


def test_explicit_encoding_pin(tmp_path):
    p = tmp_path / "x.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x,label\n1,caf\xe9\n")
    # Pin to latin-1 explicitly; should succeed without any fallback.
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path), url="latin-1")
    df, _ = load_concat_csvs(spec, label="label")
    assert df.loc[0, "label"] == "café"


def test_schema_tolerant_concat(tmp_path):
    # Two CSVs with overlapping but different schemas — concat aligns
    # on column names, fills missing with NaN.
    _write_csv(tmp_path / "wifi.csv",       "a,b,label\n1,2,attack\n")
    _write_csv(tmp_path / "bluetooth.csv",  "a,c,label\n3,4,benign\n")
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path))
    df, _ = load_concat_csvs(spec, label="label")
    assert {"a", "b", "c", "label"} == set(df.columns)
    assert len(df) == 2
    # Each CSV's missing column shows up as NaN
    assert df["b"].isna().sum() == 1
    assert df["c"].isna().sum() == 1


def test_raises_when_directory_empty(tmp_path):
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path))
    try:
        load_concat_csvs(spec, label="label")
    except FileNotFoundError as exc:
        assert "no CSV files" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError when directory is empty")


def test_glob_max_rows_per_file_caps_load(tmp_path):
    # Two CSVs with 100 rows each. The pipe-overloaded glob caps per-file
    # reads at 10 rows — total should be 20, not 200.
    big_csv = "x,label\n" + "\n".join(f"{i},A" for i in range(100)) + "\n"
    _write_csv(tmp_path / "a.csv", big_csv)
    _write_csv(tmp_path / "b.csv", big_csv.replace(",A", ",B"))
    spec = SourceSpec(
        kind="concat_csvs",
        cached_at=str(tmp_path),
        glob="*.csv|max_rows_per_file=10",
    )
    df, _ = load_concat_csvs(spec, label="label")
    assert len(df) == 20                                # 10 from each file
    assert set(df["label"].unique()) == {"A", "B"}


def test_glob_memory_budget_aborts(tmp_path):
    # Tiny budget (1 byte) → guard fires after the first file.
    _write_csv(tmp_path / "a.csv", "x,label\n1,A\n")
    _write_csv(tmp_path / "b.csv", "x,label\n2,B\n")
    spec = SourceSpec(
        kind="concat_csvs",
        cached_at=str(tmp_path),
        glob="*.csv|memory_budget_gb=0.0000001",
    )
    from tabprep.core.memguard import RAMBudgetExceeded
    try:
        load_concat_csvs(spec, label="label")
    except RAMBudgetExceeded as exc:
        assert "concat_csvs" in str(exc)
    else:
        raise AssertionError("expected RAMBudgetExceeded with tiny budget")


def test_glob_default_pattern_when_glob_unset(tmp_path):
    # Behaviour without `glob` should be identical to the legacy code path.
    _write_csv(tmp_path / "a.csv", "x,label\n1,A\n")
    spec = SourceSpec(kind="concat_csvs", cached_at=str(tmp_path))
    df, _ = load_concat_csvs(spec, label="label")
    assert df["label"].tolist() == ["A"]
