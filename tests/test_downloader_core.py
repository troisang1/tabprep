"""Unit tests for the pure helpers in `tabprep/core/downloader.py`.

We don't exercise `_stream_download` or `download_and_extract` here —
those touch the network. Their archive-extraction branches are covered
indirectly by the iot23 and openml dataset tests via mocked sklearn
fetches and pre-staged archives.
"""
from __future__ import annotations

import pytest

from tabprep.core.downloader import (
    _has_data,
    derive_target_name,
    detect_archive_format,
)


# ---------------------------------------------------------------------------
# detect_archive_format
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://x.com/data.tar.gz", "tar.gz"),
    ("https://x.com/data.tgz", "tar.gz"),
    ("https://x.com/data.tar", "tar"),
    ("https://x.com/data.zip", "zip"),
    ("https://x.com/data.gz", "gz"),
    ("https://x.com/data.csv", "none"),
    ("https://x.com/data.bin", "none"),
    # Capitalisation must be tolerated.
    ("https://x.com/DATA.TAR.GZ", "tar.gz"),
    ("https://x.com/DATA.ZIP", "zip"),
])
def test_detect_archive_format_from_url_suffix(url, expected):
    assert detect_archive_format(url) == expected


def test_detect_archive_format_strips_querystring():
    assert detect_archive_format(
        "https://x.com/dl/data.tar.gz?token=abc&foo=bar"
    ) == "tar.gz"


def test_detect_archive_format_override_takes_precedence():
    """The download endpoint may not have a recognisable extension
    (`.../download/123`); the override lets the profile pin the format."""
    assert detect_archive_format(
        "https://x.com/dl/123", override="zip"
    ) == "zip"


def test_detect_archive_format_invalid_override_raises():
    with pytest.raises(ValueError, match="unsupported archive_format"):
        detect_archive_format("https://x.com/data.csv", override="rar")


# ---------------------------------------------------------------------------
# _has_data
# ---------------------------------------------------------------------------

def test_has_data_false_on_missing_path(tmp_path):
    assert _has_data(tmp_path / "nope") is False


def test_has_data_false_on_empty_dir(tmp_path):
    (tmp_path / "empty").mkdir()
    assert _has_data(tmp_path / "empty") is False


def test_has_data_false_on_dir_with_only_empty_files(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "empty.txt").write_bytes(b"")
    assert _has_data(d) is False


def test_has_data_true_when_dir_has_nonzero_file(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "real.csv").write_text("a,b\n1,2\n")
    assert _has_data(d) is True


def test_has_data_true_when_path_is_a_nonempty_file(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("hello")
    assert _has_data(f) is True


def test_has_data_recurses_into_subdirs(tmp_path):
    d = tmp_path / "d"
    nested = d / "subdir" / "deep"
    nested.mkdir(parents=True)
    (nested / "data.csv").write_text("ok")
    assert _has_data(d) is True


# ---------------------------------------------------------------------------
# derive_target_name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    # Plain file URLs.
    ("https://example.com/data.csv", "data.csv"),
    ("https://example.com/folder/file.tar.gz", "file.tar.gz"),
    # Skip the trailing 'content' / 'download' segment (Zenodo-style).
    ("https://zenodo.org/records/123/files/data.csv/content", "data.csv"),
    ("https://example.com/path/file.zip/download", "file.zip"),
    # Querystring stripped before name detection.
    ("https://example.com/data.csv?token=abc", "data.csv"),
    # Path with no extension anywhere → fall back to last path segment
    # (NOT the host, even though the host has a dot).
    ("https://example.com/raw_data", "raw_data"),
    # Empty / root path → final fallback.
    ("https://example.com/", "downloaded.bin"),
    ("https://example.com", "downloaded.bin"),
    # Host with a port — the port is part of netloc, not path; ignored.
    ("https://example.com:8080/data.csv", "data.csv"),
    # Fragment ignored.
    ("https://example.com/data.csv#section", "data.csv"),
    # URL-encoded characters are decoded so the local filename matches
    # what a browser would save (KDDTrain%2B.txt → KDDTrain+.txt).
    ("https://raw.githubusercontent.com/x/y/master/KDDTrain%2B.txt",
     "KDDTrain+.txt"),
    ("https://example.com/path/with%20space.csv", "with space.csv"),
])
def test_derive_target_name(url, expected):
    assert derive_target_name(url) == expected
