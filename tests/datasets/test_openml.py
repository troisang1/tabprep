"""Unit tests for the openml dataset family package — loader and downloader.

The actual sklearn `fetch_openml` call is mocked: tests must not hit the
network. We patch the import path in `tabprep.datasets.openml.loader`
and `.downloader` so the real sklearn isn't reached even by accident.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from tabprep.datasets import DOWNLOADER_REGISTRY, LOADER_REGISTRY
from tabprep.datasets.openml import OpenMLDownloader, OpenMLLoader


# ---------- registration ---------------------------------------------------

def test_openml_loader_is_registered():
    assert "openml" in LOADER_REGISTRY
    assert LOADER_REGISTRY["openml"] is OpenMLLoader


def test_openml_downloader_is_registered():
    assert "openml" in DOWNLOADER_REGISTRY
    assert DOWNLOADER_REGISTRY["openml"] is OpenMLDownloader


# ---------- class-level metadata ------------------------------------------

def test_openml_downloader_class_attributes():
    """The downloader's metadata is a public contract surfaced in the
    package README and CLI output. Pin it.
    """
    assert OpenMLDownloader.is_supported is True
    assert "openml.org" in OpenMLDownloader.landing_url
    assert "CC-BY" in OpenMLDownloader.licence_note
    assert OpenMLDownloader.DEFAULT_VERSION == 1
    assert OpenMLDownloader.SENTINEL == "_complete"


# ---------- OpenMLLoader.load (mocked fetch_openml) -----------------------

def _install_fake_fetch_openml(monkeypatch, df: pd.DataFrame, target: pd.Series):
    """Patch sklearn.datasets.fetch_openml so the loader sees our fixture
    instead of a real network response. The function is imported inside
    `load()`, so we need to patch the module attribute used at lookup time.
    """
    bunch = types.SimpleNamespace(data=df.copy(), target=target.copy())

    def fake_fetch(name, version=1, as_frame=True, parser="auto"):
        fake_fetch.last_call = {"name": name, "version": version,
                                "as_frame": as_frame, "parser": parser}
        return bunch

    fake_fetch.last_call = None  # type: ignore[attr-defined]

    # `from sklearn.datasets import fetch_openml` inside load() resolves
    # against sys.modules['sklearn.datasets'] — patch there.
    sk_datasets = sys.modules.setdefault("sklearn.datasets", types.ModuleType("sklearn.datasets"))
    monkeypatch.setattr(sk_datasets, "fetch_openml", fake_fetch, raising=False)
    return fake_fetch


def test_load_returns_df_and_label(monkeypatch, tmp_path):
    feats = pd.DataFrame({"x1": [0.1, 0.2, 0.3], "x2": [10, 20, 30]})
    target = pd.Series(["a", "b", "a"])
    fake = _install_fake_fetch_openml(monkeypatch, feats, target)

    df, label = OpenMLLoader().load(
        tmp_path / "raw/openml/pendigits/", "label",
        openml_name="pendigits", openml_version=1,
    )

    assert label == "label"
    assert list(df.columns) == ["x1", "x2", "label"]
    assert len(df) == 3
    assert df["label"].tolist() == ["a", "b", "a"]
    # Loader forwards openml_name and version to fetch_openml.
    assert fake.last_call["name"] == "pendigits"
    assert fake.last_call["version"] == 1
    assert fake.last_call["as_frame"] is True
    assert fake.last_call["parser"] == "auto"


def test_load_falls_back_to_cached_at_tail(monkeypatch, tmp_path):
    """When `openml_name` isn't in loader_options, derive it from the
    tail of cached_at — this is the same convention the downloader uses.
    """
    feats = pd.DataFrame({"a": [1, 2]})
    target = pd.Series([7, 8])
    fake = _install_fake_fetch_openml(monkeypatch, feats, target)

    raw_dir = tmp_path / "raw/openml/letter"
    raw_dir.mkdir(parents=True)
    df, _ = OpenMLLoader().load(raw_dir, "label")
    assert fake.last_call["name"] == "letter"
    # Target coerced to string for the label column.
    assert df["label"].tolist() == ["7", "8"]


def test_load_raises_when_name_unknown(monkeypatch, tmp_path):
    """An empty-string tail with no openml_name override should error
    clearly rather than fetching nothing.
    """
    _install_fake_fetch_openml(monkeypatch, pd.DataFrame({"a": [1]}), pd.Series([0]))
    # Path("") has empty .name — simulate that by passing a path that
    # ends with a separator.
    with pytest.raises(ValueError, match="openml_name"):
        OpenMLLoader().load(Path(""), "label")


# ---------- OpenMLDownloader.download (mocked) ----------------------------

def test_download_writes_marker_and_calls_fetch(monkeypatch, tmp_path):
    feats = pd.DataFrame({"a": [1]})
    fake = _install_fake_fetch_openml(monkeypatch, feats, pd.Series([0]))

    dest = tmp_path / "raw/openml/pendigits"
    OpenMLDownloader().download(dest)

    marker = dest / "_complete"
    assert marker.is_file()
    # Marker is non-empty (contains the dataset name) so the inherited
    # `is_cache_populated` check via `_has_data` (>0 byte) also passes.
    assert marker.stat().st_size > 0
    assert "pendigits" in marker.read_text()
    assert fake.last_call["name"] == "pendigits"
    assert fake.last_call["version"] == 1


def test_download_is_idempotent_on_marker(monkeypatch, tmp_path):
    """If `_complete` already exists, `fetch_openml` must not be called."""
    dest = tmp_path / "raw/openml/letter"
    dest.mkdir(parents=True)
    (dest / "_complete").touch()

    fake = _install_fake_fetch_openml(monkeypatch, pd.DataFrame({"a": [1]}), pd.Series([0]))
    OpenMLDownloader().download(dest)
    assert fake.last_call is None  # never called


def test_download_raises_on_empty_tail(monkeypatch, tmp_path):
    _install_fake_fetch_openml(monkeypatch, pd.DataFrame({"a": [1]}), pd.Series([0]))
    # Path with empty .name — pass the project root which has no tail.
    with pytest.raises(RuntimeError, match="cannot infer dataset name"):
        OpenMLDownloader().download(Path("/"))
