"""Cache-hit audit: downloader idempotency when cached_at is populated.

Goal: when the user has pre-staged a dataset (manually downloaded,
extracted into `raw/<name>/`), running `tabprep prepare --profile <name>`
must NOT trigger a network call. The framework's idempotency check
should detect existing data and skip the download.

This test file pins that contract for every downloader type:

  HTTPArchiveDownloader  — skip if any non-empty file under cached_at
  HTTPMultiURLDownloader — skip per-URL if target_name file exists
  v0.4 _ensure_cached    — same as HTTPArchiveDownloader (delegates
                           to download_and_extract)
  OpenML/Covertype       — skip if `_complete` marker exists
                           (sklearn uses its own ~/scikit_learn_data
                           cache; our cached_at is just a sentinel)
  FormGatedDownloader    — always raises (no auto-fetch)

Each test monkey-patches the network helper to record call counts;
the assertion is that the patched helper is **never invoked** when
cached_at is already populated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import tabprep.core.downloader as core_dl


# ---------------------------------------------------------------------------
# Helpers: stub the actual network helpers so any unintended call crashes.
# ---------------------------------------------------------------------------

@pytest.fixture
def no_net(monkeypatch):
    """Replace `_stream_download` and `requests.get` with stubs that
    raise on call. If a downloader correctly hits its cache, neither
    is invoked."""
    captured: list[str] = []

    def fake_stream(url, dest):
        captured.append(f"stream:{url}")
        raise AssertionError(
            f"unexpected network call to {url} — should have been a cache hit"
        )

    monkeypatch.setattr(core_dl, "_stream_download", fake_stream)
    return captured


# ---------------------------------------------------------------------------
# v0.4 path / HTTPArchiveDownloader: any non-empty file = cache hit
# ---------------------------------------------------------------------------

def test_http_archive_skips_when_cached_at_has_data(no_net, tmp_path):
    """`HTTPArchiveDownloader.download()` ultimately delegates to
    `download_and_extract`, which checks `_has_data(cached_at)` and
    skips if any non-empty file is under it."""
    from tabprep.datasets._base import HTTPArchiveDownloader

    # Pre-stage some data.
    (tmp_path / "fake_data.csv").write_text("col1,col2\n1,2\n3,4\n")

    class _Probe(HTTPArchiveDownloader):
        url = "https://example.com/data.zip"
        archive_format = "zip"

    _Probe().download(tmp_path)
    assert no_net == []                      # no network call


def test_http_archive_skips_when_cached_at_has_nested_data(no_net, tmp_path):
    """`_has_data` recurses into subdirectories — pre-staged data in a
    subdir still counts as a cache hit."""
    from tabprep.datasets._base import HTTPArchiveDownloader

    nested = tmp_path / "extracted" / "deep"
    nested.mkdir(parents=True)
    (nested / "data.csv").write_text("ok\n1\n")

    class _Probe(HTTPArchiveDownloader):
        url = "https://example.com/data.zip"

    _Probe().download(tmp_path)
    assert no_net == []


def test_http_archive_does_NOT_skip_when_cached_at_is_empty(monkeypatch, tmp_path):
    """If cached_at exists but is empty, the downloader does call out
    to the network helper. Pin this so we don't accidentally make the
    cache-hit check too permissive."""
    from tabprep.datasets._base import HTTPArchiveDownloader

    captured = {"called": False}

    def fake_stream(url, dest):
        captured["called"] = True
        Path(dest).write_text("downloaded")
        return ""  # sha256 placeholder

    monkeypatch.setattr(core_dl, "_stream_download", fake_stream)

    class _Probe(HTTPArchiveDownloader):
        url = "https://example.com/data.csv"
        archive_format = "none"

    tmp_path.mkdir(exist_ok=True)
    _Probe().download(tmp_path)
    assert captured["called"] is True       # NOT a cache hit; network was called


# ---------------------------------------------------------------------------
# HTTPMultiURLDownloader: per-URL target_name check
# ---------------------------------------------------------------------------

def test_http_multi_url_skips_when_all_targets_present(no_net, tmp_path):
    """`HTTPMultiURLDownloader` uses `derive_target_name` per-URL and
    delegates to `download_and_extract`, which short-circuits if the
    `cached_at / target_name` file already exists with size > 0."""
    from tabprep.datasets._base import HTTPMultiURLDownloader

    # Pre-stage the target files (matching what derive_target_name
    # would produce for each URL).
    (tmp_path / "file_a.csv").write_text("col\n1\n")
    (tmp_path / "file_b.csv").write_text("col\n2\n")

    class _Probe(HTTPMultiURLDownloader):
        urls = (
            "https://example.com/file_a.csv",
            "https://example.com/file_b.csv",
        )

    _Probe().download(tmp_path)
    assert no_net == []


# ---------------------------------------------------------------------------
# OpenML / Covertype downloaders: `_complete` marker
# ---------------------------------------------------------------------------

def test_openml_downloader_skips_when_marker_present(monkeypatch, tmp_path):
    """`OpenMLDownloader` only checks for the `_complete` marker file.
    If present, it does not call sklearn.fetch_openml."""
    from tabprep.datasets.openml import OpenMLDownloader

    fetch_called = {"yes": False}
    import types
    sk_datasets = sys.modules.setdefault(
        "sklearn.datasets", types.ModuleType("sklearn.datasets")
    )

    def fake_fetch(*args, **kwargs):
        fetch_called["yes"] = True

    monkeypatch.setattr(sk_datasets, "fetch_openml", fake_fetch, raising=False)

    dest = tmp_path / "raw" / "openml" / "pendigits"
    dest.mkdir(parents=True)
    (dest / "_complete").write_text("openml:pendigits\n")

    OpenMLDownloader().download(dest)
    assert fetch_called["yes"] is False


def test_covertype_downloader_skips_when_marker_present(monkeypatch, tmp_path):
    """Same contract as OpenML — `_complete` marker present → skip."""
    from tabprep.datasets.covertype import CovertypeDownloader

    fetch_called = {"yes": False}
    import types
    sk_datasets = sys.modules.setdefault(
        "sklearn.datasets", types.ModuleType("sklearn.datasets")
    )

    def fake_fetch(*args, **kwargs):
        fetch_called["yes"] = True

    monkeypatch.setattr(sk_datasets, "fetch_covtype", fake_fetch, raising=False)

    dest = tmp_path / "raw" / "covertype"
    dest.mkdir(parents=True)
    (dest / "_complete").write_text("covertype\n")

    CovertypeDownloader().download(dest)
    assert fetch_called["yes"] is False


# ---------------------------------------------------------------------------
# FormGatedDownloader: always raises (no auto-fetch path)
# ---------------------------------------------------------------------------

def test_form_gated_downloader_always_refuses(tmp_path):
    """`FormGatedDownloader` is intentionally never auto-fetched —
    it always raises regardless of cached_at state."""
    from tabprep.datasets._base import FormGatedDownloader

    class _Probe(FormGatedDownloader):
        landing_url = "https://example.com/landing"
        licence_note = "Test refusal"

    # Even with pre-staged data, FormGated downloaders refuse.
    (tmp_path / "fake_data.csv").write_text("ok\n")
    with pytest.raises(RuntimeError, match="cannot be auto-downloaded"):
        _Probe().download(tmp_path)


# ---------------------------------------------------------------------------
# v0.4 _ensure_cached path (api.py): user pre-staged data short-circuits
# ---------------------------------------------------------------------------

def test_v04_ensure_cached_skips_when_cached_at_populated(no_net, tmp_path):
    """The v0.4 legacy code path in `tabprep.api._ensure_cached`
    delegates to `download_and_extract` per-URL. With user-staged data
    in cached_at, no network call should occur."""
    from tabprep.api import _ensure_cached
    from tabprep.core.profile import (
        LabelSpec, OpSpec, OutputSpec, Profile, SourceSpec, SplitSpec,
    )

    # Pre-stage data.
    (tmp_path / "user_staged.csv").write_text("a,b\n1,2\n")

    profile = Profile(
        name="probe", version="0", description="t",
        label=LabelSpec(source_column="x"),
        pipeline=[OpSpec(op="fill_nan")],
        split=SplitSpec(),
        output=OutputSpec(),
        source=SourceSpec(
            kind="concat_csvs",
            cached_at=str(tmp_path),
            download_url="https://example.com/data.csv",
        ),
    )
    _ensure_cached(profile)
    assert no_net == []
