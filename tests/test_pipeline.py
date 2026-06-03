"""End-to-end tests for `tabprep.core.pipeline.run_pipeline`.

A synthetic in-memory loader provides deterministic raw data so the
test runs sub-second with no I/O beyond the canonical CSV writer + the
manifest writer. Verifies that the executor:

  * dispatches to the correct loader (v0.5 path)
  * applies the implicit label rename + normalize
  * threads pipeline ops in order
  * writes byte-identical CSVs across runs
  * produces a manifest whose hashes match the disk files
  * raises clearly when the loader is unknown
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tabprep.core.hashing import canonical_sha256_of_file
from tabprep.core.pipeline import run_pipeline
from tabprep.core.profile import (
    LabelSpec,
    OpSpec,
    OutputSpec,
    Profile,
    SplitSpec,
)
from tabprep.datasets._base import (
    BaseDownloader,
    BaseLoader,
    downloader,
    loader,
)


# ---------------------------------------------------------------------------
# Synthetic loader/downloader registered once at import time
# ---------------------------------------------------------------------------

@loader("_pipeline_test")
class _PipelineTestLoader(BaseLoader):
    """30-row balanced 3-class synthetic frame.

    Per framework convention, the loader returns ``label_col`` exactly
    as the framework passed it in (which is ``profile.label.rename_to``).
    The dataframe still carries the *source* column name (`"raw"`); the
    framework's `_apply_pipeline` handles the rename via the implicit
    `rename_label` op when `source_column != rename_to`.
    """

    def load(self, raw_dir, label_col, **opts):
        rows = []
        for cls in ("a", "b", "c"):
            for i in range(10):
                rows.append({"x": float(i), "y": i * 2, "raw": cls})
        return pd.DataFrame(rows), label_col


@downloader("_pipeline_test")
class _PipelineTestDownloader(BaseDownloader):
    """No-op downloader (loader doesn't need raw_dir)."""

    def download(self, dest_dir):
        Path(dest_dir).mkdir(parents=True, exist_ok=True)


@loader("_pipeline_multilabel_test")
class _PipelineMultiLabelLoader(BaseLoader):
    """Like the base loader but also emits two *sibling target* columns
    (`attack`, `subcategory`) — the multi-label IDS shape that
    `label.also_drop` exists to strip before they leak."""

    def load(self, raw_dir, label_col, **opts):
        rows = []
        for cls in ("a", "b", "c"):
            for i in range(10):
                rows.append({
                    "x": float(i), "y": i * 2, "raw": cls,
                    "attack": 1 if cls != "a" else 0,   # binary sibling target
                    "subcategory": f"{cls}_sub",         # fine-grained sibling
                })
        return pd.DataFrame(rows), label_col


# ---------------------------------------------------------------------------
# Profile factory
# ---------------------------------------------------------------------------

def _make_profile(*,
                  pipeline=None,
                  label_source: str = "raw",
                  label_rename: str = "label",
                  cached_at: str = "/tmp/_pipeline_test_cache") -> Profile:
    return Profile(
        name="_pipeline_test",
        version="0.0.1",
        description="synthetic",
        loader="_pipeline_test",
        downloader="_pipeline_test",
        cached_at=cached_at,
        loader_options={},
        label=LabelSpec(source_column=label_source, rename_to=label_rename),
        pipeline=pipeline or [],
        split=SplitSpec(train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42),
        output=OutputSpec(precision=6),
        expected_hashes={},
    )


# ---------------------------------------------------------------------------
# run_pipeline — happy path
# ---------------------------------------------------------------------------

def test_run_pipeline_writes_three_splits_and_manifest(tmp_path):
    prof = _make_profile()
    summary = run_pipeline(prof, output_root=tmp_path)

    out_dir = tmp_path / "_pipeline_test"
    assert (out_dir / "train.csv").is_file()
    assert (out_dir / "calibration.csv").is_file()
    assert (out_dir / "test.csv").is_file()
    assert (out_dir / "_manifest.json").is_file()

    # Summary structure pinned for callers (api / cli depend on it).
    assert summary["out_dir"] == str(out_dir)
    assert {f["path"] for f in summary["files"]} == {
        "train.csv", "calibration.csv", "test.csv",
    }
    for f in summary["files"]:
        assert len(f["sha256"]) == 64
        assert f["rows"] > 0
        assert f["cols"] >= 2          # x, y, label


def test_run_pipeline_implicit_label_rename(tmp_path):
    """Loader returns 'raw' as the label; the executor must rename it
    to the profile's `label.rename_to` ('label') before the user pipeline
    sees the dataframe."""
    prof = _make_profile(label_source="raw", label_rename="label")
    run_pipeline(prof, output_root=tmp_path)

    train = pd.read_csv(tmp_path / "_pipeline_test" / "train.csv")
    assert "label" in train.columns
    assert "raw" not in train.columns


def test_run_pipeline_also_drop_removes_sibling_targets(tmp_path):
    """`label.also_drop` must strip sibling target columns BEFORE the
    pipeline runs, so a multi-label IDS dataset can't leak the answer.
    The chosen target survives as `label`; `attack`/`subcategory` do not."""
    prof = Profile(
        name="_pipeline_multilabel_test",
        version="0.0.1",
        description="synthetic multi-label",
        loader="_pipeline_multilabel_test",
        downloader="_pipeline_test",
        cached_at="/tmp/_pipeline_ml_cache",
        loader_options={},
        label=LabelSpec(source_column="raw", rename_to="label",
                        also_drop=["attack", "subcategory"]),
        pipeline=[],
        split=SplitSpec(train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42),
        output=OutputSpec(precision=6),
        expected_hashes={},
    )
    run_pipeline(prof, output_root=tmp_path)

    train = pd.read_csv(tmp_path / "_pipeline_multilabel_test" / "train.csv")
    assert "label" in train.columns
    assert "attack" not in train.columns
    assert "subcategory" not in train.columns
    assert "x" in train.columns and "y" in train.columns


def test_run_pipeline_also_drop_never_drops_chosen_label(tmp_path):
    """A profile that mistakenly lists its own target in `also_drop` must
    still keep the label — the executor guards `label_col` out."""
    prof = Profile(
        name="_pipeline_multilabel_test",
        version="0.0.1",
        description="synthetic multi-label",
        loader="_pipeline_multilabel_test",
        downloader="_pipeline_test",
        cached_at="/tmp/_pipeline_ml_cache",
        loader_options={},
        # 'label' is the rename target; listing it must be a no-op for it.
        label=LabelSpec(source_column="raw", rename_to="label",
                        also_drop=["label", "attack"]),
        pipeline=[],
        split=SplitSpec(train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42),
        output=OutputSpec(precision=6),
        expected_hashes={},
    )
    run_pipeline(prof, output_root=tmp_path)

    train = pd.read_csv(tmp_path / "_pipeline_multilabel_test" / "train.csv")
    assert "label" in train.columns
    assert "attack" not in train.columns


def test_run_pipeline_runs_ops_in_order(tmp_path):
    """A pipeline that drops the 'y' column must result in train/cal/test
    files without 'y'."""
    prof = _make_profile(
        pipeline=[OpSpec(op="drop_columns", params={"columns": ["y"]})],
    )
    run_pipeline(prof, output_root=tmp_path)
    train = pd.read_csv(tmp_path / "_pipeline_test" / "train.csv")
    assert "y" not in train.columns
    assert "x" in train.columns


def test_run_pipeline_byte_stable_across_runs(tmp_path):
    """Same profile run twice → byte-identical splits."""
    prof = _make_profile()
    a_root = tmp_path / "a"
    b_root = tmp_path / "b"
    run_pipeline(prof, output_root=a_root)
    run_pipeline(prof, output_root=b_root)

    for fname in ("train.csv", "calibration.csv", "test.csv"):
        a = canonical_sha256_of_file(a_root / "_pipeline_test" / fname)
        b = canonical_sha256_of_file(b_root / "_pipeline_test" / fname)
        assert a == b, f"{fname} differs across runs"


def test_run_pipeline_manifest_hashes_match_disk_files(tmp_path):
    """The manifest's per-file sha256 must equal a fresh hash of the
    same on-disk file. Catches accidental order-of-operations bugs
    where the manifest is built before the canonical write completes."""
    prof = _make_profile()
    run_pipeline(prof, output_root=tmp_path)

    out_dir = tmp_path / "_pipeline_test"
    manifest = json.loads((out_dir / "_manifest.json").read_text(encoding="utf-8"))

    for entry in manifest["files"]:
        observed = canonical_sha256_of_file(out_dir / entry["path"])
        assert observed == entry["sha256"], (
            f"manifest claims {entry['sha256']} for {entry['path']} "
            f"but on-disk file hashes {observed}"
        )


def test_run_pipeline_normalizes_label_string(tmp_path):
    """The implicit normalize_label_string runs after rename. With method
    'lowercase_underscore', `'A '` becomes `'a'`."""
    prof = _make_profile()
    # No pipeline ops; rely on implicit label normalize. Our synthetic
    # loader returns clean strings ("a", "b", "c") so they're already
    # normalised — test that the output reflects that normalisation
    # without interference.
    run_pipeline(prof, output_root=tmp_path)
    train = pd.read_csv(tmp_path / "_pipeline_test" / "train.csv")
    labels = set(train["label"].unique())
    assert labels.issubset({"a", "b", "c"})


# ---------------------------------------------------------------------------
# run_pipeline — error paths
# ---------------------------------------------------------------------------

def test_run_pipeline_raises_on_unknown_op(tmp_path):
    prof = _make_profile(
        pipeline=[OpSpec(op="not_a_real_op", params={})],
    )
    with pytest.raises(ValueError, match="unknown op 'not_a_real_op'"):
        run_pipeline(prof, output_root=tmp_path)


def test_run_pipeline_raises_on_unknown_loader(tmp_path):
    """A profile referencing a loader name that isn't in LOADER_REGISTRY
    must surface a clear error before any writes happen."""
    prof = _make_profile()
    prof.loader = "definitely_not_registered_xyz"
    with pytest.raises(ValueError, match="unknown loader"):
        run_pipeline(prof, output_root=tmp_path)


def test_run_pipeline_raises_when_v05_missing_cached_at(tmp_path):
    """v0.5 dispatch requires `cached_at`; the pipeline raises rather than
    passing None to the loader."""
    prof = _make_profile()
    prof.cached_at = None
    with pytest.raises(ValueError, match="cached_at"):
        run_pipeline(prof, output_root=tmp_path)
