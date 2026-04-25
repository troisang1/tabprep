"""Unit tests for the covertype dataset package — loader and downloader.

`fetch_covtype` is mocked: tests must not hit the network. We patch
the function on `sklearn.datasets` so the `from sklearn.datasets import
fetch_covtype` inside the loader resolves to our fixture.
"""
from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd

from tabprep.datasets import DOWNLOADER_REGISTRY, LOADER_REGISTRY
from tabprep.datasets.covertype import CovertypeDownloader, CovertypeLoader


# ---------- registration ---------------------------------------------------

def test_covertype_loader_is_registered():
    assert "covertype" in LOADER_REGISTRY
    assert LOADER_REGISTRY["covertype"] is CovertypeLoader


def test_covertype_downloader_is_registered():
    assert "covertype" in DOWNLOADER_REGISTRY
    assert DOWNLOADER_REGISTRY["covertype"] is CovertypeDownloader


# ---------- class-level metadata ------------------------------------------

def test_covertype_downloader_class_attributes():
    assert CovertypeDownloader.is_supported is True
    assert "uci" in CovertypeDownloader.landing_url.lower() or \
           "covertype" in CovertypeDownloader.landing_url.lower()
    assert "CC-BY" in CovertypeDownloader.licence_note
    assert CovertypeDownloader.SENTINEL == "_complete"


# ---------- fake fetch_covtype helpers -----------------------------------

def _install_fake_fetch(monkeypatch, *, as_frame_payload, ndarray_payload=None):
    """Patch sklearn.datasets.fetch_covtype to return either a DataFrame
    Bunch (`as_frame_payload`) or fall through to an ndarray Bunch
    (`ndarray_payload`) when `as_frame=True` raises TypeError.
    """
    state = {"as_frame_kwarg_seen": False, "called_no_args": False}

    def fake_fetch(*args, **kwargs):
        if "as_frame" in kwargs:
            state["as_frame_kwarg_seen"] = True
            if kwargs["as_frame"] is True and ndarray_payload is not None and as_frame_payload is None:
                # Simulate an old sklearn that raises TypeError when as_frame=True.
                raise TypeError("got an unexpected keyword 'as_frame'")
            return as_frame_payload
        state["called_no_args"] = True
        return ndarray_payload

    sk_datasets = sys.modules.setdefault(
        "sklearn.datasets", types.ModuleType("sklearn.datasets")
    )
    monkeypatch.setattr(sk_datasets, "fetch_covtype", fake_fetch, raising=False)
    return fake_fetch, state


# ---------- CovertypeLoader.load (DataFrame path) -------------------------

def test_load_dataframe_path(monkeypatch, tmp_path):
    feats = pd.DataFrame({"f0": [0.1, 0.2], "f1": [3, 4]})
    target = pd.Series([1, 2])
    bunch = types.SimpleNamespace(data=feats, target=target)
    _install_fake_fetch(monkeypatch, as_frame_payload=bunch)

    df, label = CovertypeLoader().load(tmp_path, "label")

    assert label == "label"
    assert list(df.columns) == ["f0", "f1", "label"]
    # Target coerced to string.
    assert df["label"].tolist() == ["1", "2"]


# ---------- CovertypeLoader.load (ndarray fallback path) ------------------

def test_load_ndarray_fallback_with_feature_names(monkeypatch, tmp_path):
    """Older sklearn raises TypeError on as_frame=True. Loader retries
    without kwargs and reconstructs the DataFrame from ndarray + feature_names.
    """
    arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    target = np.array([10, 20])
    feature_names = ["a", "b", "c"]
    bunch = types.SimpleNamespace(data=arr, target=target, feature_names=feature_names)
    _install_fake_fetch(monkeypatch, as_frame_payload=None, ndarray_payload=bunch)

    df, _ = CovertypeLoader().load(tmp_path, "label")
    assert list(df.columns) == ["a", "b", "c", "label"]
    assert df.shape == (2, 4)
    assert df["label"].tolist() == ["10", "20"]


def test_load_ndarray_fallback_without_feature_names(monkeypatch, tmp_path):
    """When sklearn returns ndarray output AND no feature_names, the
    loader synthesises `f0`..`fN-1` so downstream ops still see
    column-name-based logic.
    """
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    target = np.array([5, 6])
    bunch = types.SimpleNamespace(data=arr, target=target)  # no feature_names
    _install_fake_fetch(monkeypatch, as_frame_payload=None, ndarray_payload=bunch)

    df, _ = CovertypeLoader().load(tmp_path, "label")
    assert list(df.columns) == ["f0", "f1", "label"]


# ---------- CovertypeDownloader -------------------------------------------

def test_download_writes_marker(monkeypatch, tmp_path):
    bunch = types.SimpleNamespace(
        data=pd.DataFrame({"f0": [1]}), target=pd.Series([0]),
    )
    _install_fake_fetch(monkeypatch, as_frame_payload=bunch)

    dest = tmp_path / "raw/covertype"
    CovertypeDownloader().download(dest)
    marker = dest / "_complete"
    assert marker.is_file()
    # Marker is non-empty so the inherited `is_cache_populated` check
    # via `_has_data` (>0 byte) also passes.
    assert marker.stat().st_size > 0


def test_download_is_idempotent_on_marker(monkeypatch, tmp_path):
    dest = tmp_path / "raw/covertype"
    dest.mkdir(parents=True)
    (dest / "_complete").touch()

    fake, state = _install_fake_fetch(
        monkeypatch,
        as_frame_payload=types.SimpleNamespace(
            data=pd.DataFrame({"f0": [1]}), target=pd.Series([0])
        ),
    )
    CovertypeDownloader().download(dest)
    # Cache hit: fetch_covtype must not have been called.
    assert state["as_frame_kwarg_seen"] is False
    assert state["called_no_args"] is False
