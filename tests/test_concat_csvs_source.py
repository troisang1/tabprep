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
