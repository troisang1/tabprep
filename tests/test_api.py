"""Unit tests for the public `tabprep` API (`tabprep/api.py`).

The tests use synthetic in-memory profiles and a stubbed loader so they
run fast and don't hit the network. The `prepare()` happy-path against
a real built-in profile is covered by the existing `tests/datasets/`
suites + the regression gate (`verify --all`); no need to duplicate.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import tabprep
from tabprep.api import (
    PrepareResult,
    list_profiles,
    load_split,
    load_splits,
    prepare,
    resolve_profile,
)
from tabprep.core.profile import (
    LabelSpec,
    OutputSpec,
    Profile,
    SplitSpec,
)
from tabprep.datasets._base import BaseDownloader, BaseLoader, downloader, loader


# ---------------------------------------------------------------------------
# Test fixtures: a tiny throwaway loader/downloader pair. The loader
# ignores raw_dir and emits a deterministic 30-row synthetic frame; the
# downloader is a no-op since the loader doesn't actually read disk.
# ---------------------------------------------------------------------------

@loader("_apitest")
class _APITestLoader(BaseLoader):
    """Synthetic loader for api tests — three-class balanced 30-row frame."""
    def load(self, raw_dir, label_col, **opts):
        rows = []
        for cls in ("a", "b", "c"):
            for i in range(10):
                rows.append({"x": float(i), "y": i * 2, label_col: cls})
        return pd.DataFrame(rows), label_col


@downloader("_apitest")
class _APITestDownloader(BaseDownloader):
    """No-op downloader. The loader doesn't read raw_dir, so there's
    nothing to fetch — but Profile validation requires `downloader:`
    whenever `loader:` is set, so we register a stub.
    """
    def download(self, dest_dir):
        Path(dest_dir).mkdir(parents=True, exist_ok=True)


def _make_synthetic_profile(name: str = "_apitest_profile",
                            cached_at: str = "/tmp/_apitest_cache") -> Profile:
    """Build a Profile in code (no YAML) for fast tests."""
    return Profile(
        name=name,
        version="0.0.1",
        description="synthetic",
        loader="_apitest",
        downloader="_apitest",
        cached_at=cached_at,
        loader_options={},
        label=LabelSpec(source_column="label", rename_to="label"),
        pipeline=[],
        split=SplitSpec(train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42),
        output=OutputSpec(precision=6),
        expected_hashes={},
    )


# ---------------------------------------------------------------------------
# resolve_profile
# ---------------------------------------------------------------------------

def test_resolve_profile_passes_through_profile_instance():
    prof = _make_synthetic_profile()
    assert resolve_profile(prof) is prof


def test_resolve_profile_loads_yaml_path(tmp_path):
    p = (Path(__file__).parent.parent / "tabprep" / "profiles"
         / "pendigits.yaml")
    prof = resolve_profile(p)
    assert prof.name == "pendigits"


def test_resolve_profile_loads_string_path():
    """A string with a path separator or `.yaml` suffix is loaded as a
    filesystem path. Use an absolute path so the test doesn't depend on
    the pytest working directory.
    """
    p = str(Path(__file__).parent.parent / "tabprep" / "profiles"
            / "pendigits.yaml")
    prof = resolve_profile(p)
    assert prof.name == "pendigits"


def test_resolve_profile_looks_up_builtin_by_name():
    prof = resolve_profile("pendigits")
    assert prof.name == "pendigits"
    assert prof.loader == "openml"


def test_resolve_profile_raises_with_helpful_message_when_unknown():
    with pytest.raises(FileNotFoundError, match="no built-in profile"):
        resolve_profile("definitely_not_a_real_profile_xyz")


def test_resolve_profile_raises_on_wrong_type():
    with pytest.raises(TypeError, match="must be str"):
        resolve_profile(42)                                       # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------

def test_list_profiles_returns_all_18_builtins():
    profiles = list_profiles()
    names = {p.name for p in profiles}
    # The 9 migrated v0.5 profiles (8 UCI + iot23) live under
    # tabprep/profiles/<name>.yaml; the remaining 9 IDS profiles still
    # live under tabprep/profiles/builtin/ pending Phase 4.
    expected = {
        "5g_nidd", "cic_ddos2019", "cic_iomt2024", "cicids2018",
        "ciciot2023", "covertype", "edge_iiot", "har", "iot23",
        "letter", "nbaiot", "optdigits", "pendigits", "satimage",
        "segment", "texture", "ton_iot", "unsw_nb15",
    }
    assert expected.issubset(names)
    assert len(profiles) == 18


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------

def test_prepare_writes_three_csvs_and_manifest(tmp_path):
    prof = _make_synthetic_profile()
    result = prepare(prof, output_dir=tmp_path, quiet=True)

    assert isinstance(result, PrepareResult)
    assert result.train.is_file()
    assert result.calibration.is_file()
    assert result.test.is_file()
    assert result.manifest_path.is_file()
    assert set(result.sha256.keys()) == {"train.csv", "calibration.csv", "test.csv"}
    # No expected_hashes pinned on the synthetic profile.
    assert result.verified is None


def test_prepare_load_returns_dataframe(tmp_path):
    result = prepare(_make_synthetic_profile(), output_dir=tmp_path, quiet=True)
    df = result.load("train")
    assert isinstance(df, pd.DataFrame)
    assert "label" in df.columns
    # 30 rows total, 60/20/20 → 18 train rows.
    assert len(df) == 18


def test_prepare_load_all_returns_three_dataframes(tmp_path):
    result = prepare(_make_synthetic_profile(), output_dir=tmp_path, quiet=True)
    train, cal, test = result.load_all()
    assert len(train) + len(cal) + len(test) == 30


def test_prepare_load_rejects_unknown_split(tmp_path):
    result = prepare(_make_synthetic_profile(), output_dir=tmp_path, quiet=True)
    with pytest.raises(ValueError, match="unknown split"):
        result.load("validation")


def test_prepare_does_not_mutate_caller_profile(tmp_path):
    """Regression test: prepare() must not mutate a Profile instance the
    caller passes in. Previously it resolved `cached_at` to an absolute
    path in place, surprising callers who held a reference."""
    prof = _make_synthetic_profile(cached_at="raw/_apitest_cache")
    cached_before = prof.cached_at
    pipeline_before = prof.pipeline

    prepare(prof, output_dir=tmp_path, skip_pipeline=True, quiet=True)

    assert prof.cached_at == cached_before
    assert prof.pipeline is pipeline_before


def test_prepare_skip_pipeline_bypasses_user_ops(tmp_path):
    """skip_pipeline=True should skip user ops but still write splits."""
    prof = _make_synthetic_profile()
    # No-op pipeline already; this just confirms the flag doesn't break anything.
    result = prepare(prof, output_dir=tmp_path, skip_pipeline=True, quiet=True)
    assert result.train.is_file()
    df = result.load("train")
    assert "label" in df.columns


# ---------------------------------------------------------------------------
# load_splits / load_split
# ---------------------------------------------------------------------------

def test_load_splits_returns_three_dataframes(tmp_path):
    train, cal, test = load_splits(
        _make_synthetic_profile(), output_dir=tmp_path, quiet=True,
    )
    assert all(isinstance(d, pd.DataFrame) for d in (train, cal, test))
    assert len(train) + len(cal) + len(test) == 30


def test_load_splits_uses_cache_on_second_call(tmp_path, monkeypatch):
    """When use_cache=True (default), a second call must NOT re-run prepare."""
    prof = _make_synthetic_profile()
    # First call materialises the CSVs.
    load_splits(prof, output_dir=tmp_path, quiet=True)

    # Wrap run_pipeline so the second call would crash if it ran.
    import tabprep.api as api_module
    call_log = {"prepare_called": False}
    real_prepare = api_module.prepare

    def spy_prepare(*args, **kwargs):
        call_log["prepare_called"] = True
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(api_module, "prepare", spy_prepare)
    train, cal, test = load_splits(prof, output_dir=tmp_path, quiet=True)
    assert call_log["prepare_called"] is False
    assert len(train) + len(cal) + len(test) == 30


def test_load_splits_use_cache_false_forces_rebuild(tmp_path, monkeypatch):
    prof = _make_synthetic_profile()
    load_splits(prof, output_dir=tmp_path, quiet=True)

    import tabprep.api as api_module
    call_log = {"prepare_called": False}
    real_prepare = api_module.prepare

    def spy_prepare(*args, **kwargs):
        call_log["prepare_called"] = True
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(api_module, "prepare", spy_prepare)
    load_splits(prof, output_dir=tmp_path, use_cache=False, quiet=True)
    assert call_log["prepare_called"] is True


def test_load_split_train_calibration_test(tmp_path):
    prof = _make_synthetic_profile()
    train = load_split(prof, "train", output_dir=tmp_path, quiet=True)
    cal = load_split(prof, "calibration", output_dir=tmp_path, quiet=True)
    cal_alias = load_split(prof, "cal", output_dir=tmp_path, quiet=True)
    test = load_split(prof, "test", output_dir=tmp_path, quiet=True)

    assert len(train) == 18
    assert len(cal) == 6
    assert len(cal_alias) == 6
    assert len(test) == 6
    pd.testing.assert_frame_equal(cal, cal_alias)


def test_load_split_rejects_unknown_split(tmp_path):
    prof = _make_synthetic_profile()
    with pytest.raises(ValueError, match="unknown split"):
        load_split(prof, "validation", output_dir=tmp_path, quiet=True)


# ---------------------------------------------------------------------------
# Top-level re-exports (the user-facing surface)
# ---------------------------------------------------------------------------

def test_top_level_exports():
    assert tabprep.prepare is prepare
    assert tabprep.load_splits is load_splits
    assert tabprep.load_split is load_split
    assert tabprep.list_profiles is list_profiles
    assert tabprep.PrepareResult is PrepareResult
