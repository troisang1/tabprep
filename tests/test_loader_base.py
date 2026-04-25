"""Tests for `tabprep.datasets._base.BaseLoader` utility methods."""
from __future__ import annotations


import numpy as np
import pandas as pd
import pytest

from tabprep.datasets._base import BaseLoader


# A minimal concrete subclass to instantiate when tests need it.
class _StubLoader(BaseLoader):
    def load(self, raw_dir, label_col, **opts):
        raise NotImplementedError


# ---------- recursive_glob -------------------------------------------------

def test_recursive_glob_finds_nested_files(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    (tmp_path / "sub" / "b.csv").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "sub" / "b.csv").write_text("x\n2\n")
    (tmp_path / "sub" / "deep" / "c.csv").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "sub" / "deep" / "c.csv").write_text("x\n3\n")
    files = BaseLoader.recursive_glob(tmp_path, ("*.csv",))
    assert len(files) == 3
    # Sorted by full path
    names = [f.name for f in files]
    assert names == sorted(names)


def test_recursive_glob_case_insensitive_extension(tmp_path):
    (tmp_path / "lower.csv").write_text("x\n1\n")
    (tmp_path / "upper.CSV").write_text("x\n2\n")
    files = BaseLoader.recursive_glob(tmp_path, ("*.csv",))
    assert len(files) == 2


def test_recursive_glob_multiple_patterns(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    (tmp_path / "b.tsv").write_text("x\n2\n")
    (tmp_path / "c.txt").write_text("ignored")
    files = BaseLoader.recursive_glob(tmp_path, ("*.csv", "*.tsv"))
    assert len(files) == 2
    assert {f.suffix.lower() for f in files} == {".csv", ".tsv"}


def test_recursive_glob_raises_on_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        BaseLoader.recursive_glob(tmp_path / "does-not-exist", ("*.csv",))


# ---------- read_csv_with_encoding_fallback -------------------------------

def test_encoding_fallback_to_latin1(tmp_path):
    p = tmp_path / "latin.csv"
    p.write_bytes(b"x,label\n1,caf\xe9\n")
    df = BaseLoader.read_csv_with_encoding_fallback(p)
    assert df.loc[0, "label"] == "café"


def test_encoding_explicit_pin(tmp_path):
    p = tmp_path / "x.csv"
    p.write_bytes(b"x,label\n1,caf\xe9\n")
    df = BaseLoader.read_csv_with_encoding_fallback(p, encodings=("latin-1",))
    assert df.loc[0, "label"] == "café"


def test_encoding_fallback_raises_when_all_fail(tmp_path):
    p = tmp_path / "weird.csv"
    p.write_bytes(b"\xff\xfe\x00\x00")  # nonsensical
    with pytest.raises(RuntimeError, match="could not decode"):
        BaseLoader.read_csv_with_encoding_fallback(p, encodings=("ascii",))


# ---------- read_head_n ----------------------------------------------------

def test_read_head_n(tmp_path):
    p = tmp_path / "big.csv"
    p.write_text("x\n" + "\n".join(str(i) for i in range(1000)) + "\n")
    df = BaseLoader.read_head_n(p, n=10)
    assert len(df) == 10
    assert df["x"].tolist() == list(range(10))


# ---------- chunked_csv_iter -----------------------------------------------

def test_chunked_csv_iter(tmp_path):
    p = tmp_path / "big.csv"
    p.write_text("x\n" + "\n".join(str(i) for i in range(250)) + "\n")
    chunks = list(BaseLoader.chunked_csv_iter(p, chunksize=100))
    assert len(chunks) == 3                              # 100 + 100 + 50
    assert sum(len(c) for c in chunks) == 250


# ---------- stratified_fraction_sample (option-b semantics) ---------------

def test_stratified_fraction_preserves_distribution():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "x": rng.normal(size=1000),
        "label": (["a"] * 700) + (["b"] * 200) + (["c"] * 100),
    })
    out = BaseLoader.stratified_fraction_sample(
        df, label_col="label", fraction=0.10, seed=42)
    counts = out["label"].value_counts()
    # 700 * 0.10 = 70, 200 * 0.10 = 20, 100 * 0.10 = 10
    assert counts["a"] == 70
    assert counts["b"] == 20
    assert counts["c"] == 10


def test_stratified_fraction_floor_keeps_tiny_class():
    df = pd.DataFrame({
        "x": list(range(101)),
        "label": (["a"] * 100) + ["rare"],
    })
    out = BaseLoader.stratified_fraction_sample(
        df, label_col="label", fraction=0.05, seed=42)
    # 100 * 0.05 = 5 'a' rows; rare has floor=1
    counts = out["label"].value_counts()
    assert counts["a"] == 5
    assert counts["rare"] == 1


def test_stratified_fraction_deterministic():
    df = pd.DataFrame({
        "x": list(range(100)),
        "label": (["a"] * 50) + (["b"] * 50),
    })
    a = BaseLoader.stratified_fraction_sample(
        df, label_col="label", fraction=0.5, seed=42)
    b = BaseLoader.stratified_fraction_sample(
        df, label_col="label", fraction=0.5, seed=42)
    pd.testing.assert_frame_equal(a, b)


def test_stratified_fraction_one_returns_full_distribution():
    df = pd.DataFrame({
        "x": list(range(50)),
        "label": (["a"] * 30) + (["b"] * 20),
    })
    out = BaseLoader.stratified_fraction_sample(
        df, label_col="label", fraction=1.0, seed=42)
    assert len(out) == 50
    assert out["label"].value_counts()["a"] == 30
    assert out["label"].value_counts()["b"] == 20


def test_stratified_fraction_rejects_invalid_fraction():
    df = pd.DataFrame({"x": [1, 2], "label": ["a", "b"]})
    with pytest.raises(ValueError):
        BaseLoader.stratified_fraction_sample(df, label_col="label",
                                              fraction=0.0, seed=42)
    with pytest.raises(ValueError):
        BaseLoader.stratified_fraction_sample(df, label_col="label",
                                              fraction=1.5, seed=42)


# ---------- cap_per_class --------------------------------------------------

def test_cap_per_class_balances_classes():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "x": rng.normal(size=1000),
        "label": (["a"] * 600) + (["b"] * 300) + (["c"] * 100),
    })
    out = BaseLoader.cap_per_class(df, label_col="label", cap=50, seed=42)
    counts = out["label"].value_counts()
    assert all(c == 50 for c in counts)


def test_cap_per_class_keeps_small_classes_whole():
    df = pd.DataFrame({
        "x": list(range(20)),
        "label": (["a"] * 5) + (["b"] * 15),
    })
    out = BaseLoader.cap_per_class(df, label_col="label", cap=10, seed=42)
    assert out["label"].value_counts()["a"] == 5    # smaller than cap, kept whole
    assert out["label"].value_counts()["b"] == 10


# ---------- registries -----------------------------------------------------

def test_loader_registry_rejects_non_subclass():
    from tabprep.datasets._base import loader as loader_decorator
    with pytest.raises(TypeError, match="must subclass BaseLoader"):
        @loader_decorator("_not_a_loader")
        class NotALoader:
            pass


def test_downloader_registry_rejects_non_subclass():
    from tabprep.datasets._base import downloader as downloader_decorator
    with pytest.raises(TypeError, match="must subclass BaseDownloader"):
        @downloader_decorator("_not_a_downloader")
        class NotADownloader:
            pass
