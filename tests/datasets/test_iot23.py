"""Unit tests for the iot23 dataset package — loader and downloader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.datasets import DOWNLOADER_REGISTRY, LOADER_REGISTRY
from tabprep.datasets.iot23 import IoT23Downloader, IoT23Loader
from tabprep.datasets.iot23.loader import _parse_zeek_fields_header


# A minimal but realistic Zeek conn.log.labeled fragment matching IoT-23's
# quirky mixed-tab/space layout: 21 tab-separated fields, then the last
# token contains "tunnel_parents", "label", "detailed-label" separated by
# spaces.
_SAMPLE = (
    "#separator \\x09\n"
    "#set_separator\t,\n"
    "#empty_field\t(empty)\n"
    "#unset_field\t-\n"
    "#path\tconn\n"
    "#open\t2018-12-21-16-13-43\n"
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p"
    "\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state"
    "\tlocal_orig\tlocal_resp\tmissed_bytes\thistory\torig_pkts"
    "\torig_ip_bytes\tresp_pkts\tresp_ip_bytes"
    "\ttunnel_parents   label   detailed-label\n"
    "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring"
    "\tinterval\tcount\tcount\tstring\tbool\tbool\tcount\tstring"
    "\tcount\tcount\tcount\tcount"
    "\tset[string]   string   string\n"
    "1545379977.0\tCw7Y\t192.168.1.1\t49259\t10.0.0.1\t23\ttcp\t-"
    "\t-\t-\t-\tS0\t-\t-\t0\tS\t1\t44\t0\t0"
    "\t-   Malicious   PartOfAHorizontalPortScan\n"
    "1545379980.0\tCxQ8\t192.168.1.1\t49260\t10.0.0.2\t80\ttcp\thttp"
    "\t1.5\t250\t800\tSF\t-\t-\t0\tShADdfFa\t8\t450\t6\t1200"
    "\t-   Benign   -\n"
    "1545379985.0\tDp1z\t192.168.1.1\t49261\t10.0.0.3\t1900\tudp\t-"
    "\t0.1\t44\t0\tS0\t-\t-\t0\tD\t1\t72\t0\t0"
    "\t-   Malicious   Mirai\n"
)


def _write_capture(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------- registration ---------------------------------------------------

def test_iot23_loader_is_registered():
    assert "iot23" in LOADER_REGISTRY
    assert LOADER_REGISTRY["iot23"] is IoT23Loader


def test_iot23_downloader_is_registered():
    assert "iot23" in DOWNLOADER_REGISTRY
    assert DOWNLOADER_REGISTRY["iot23"] is IoT23Downloader


# ---------- _parse_zeek_fields_header ------------------------------------

def test_zeek_fields_header_handles_iot23_quirk(tmp_path):
    p = tmp_path / "x.labeled"
    _write_capture(p, _SAMPLE)
    fields = _parse_zeek_fields_header(p)
    # The mixed-tab-space last token must split into THREE fields,
    # not be left as a single string.
    assert "tunnel_parents" in fields
    assert "label" in fields
    assert "detailed-label" in fields
    # Sanity: the standard prefix is intact
    assert fields[:5] == ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h"]


def test_zeek_fields_header_raises_when_no_fields_line(tmp_path):
    p = tmp_path / "broken.labeled"
    p.write_text("# nothing here\nrandom data\n", encoding="utf-8")
    try:
        _parse_zeek_fields_header(p)
    except RuntimeError as exc:
        assert "no #fields header" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


# ---------- IoT23Loader.load ----------------------------------------------

def test_load_single_capture(tmp_path):
    _write_capture(tmp_path / "captureA" / "conn.log.labeled", _SAMPLE)
    loader = IoT23Loader()
    df, label = loader.load(tmp_path, "label")
    assert label == "label"
    assert len(df) == 3
    assert "ts" in df.columns
    assert "id.orig_h" in df.columns
    assert "label" in df.columns
    assert "detailed-label" in df.columns
    # Sentinel "-" parsed as NaN
    assert pd.isna(df.loc[0, "service"])
    # Real values intact
    assert df.loc[1, "service"] == "http"


def test_load_concatenates_multiple_captures(tmp_path):
    _write_capture(tmp_path / "A" / "conn.log.labeled", _SAMPLE)
    _write_capture(tmp_path / "B" / "conn.log.labeled", _SAMPLE)
    loader = IoT23Loader()
    df, _ = loader.load(tmp_path, "label")
    assert len(df) == 6                                    # 2 captures × 3 rows


def test_load_per_file_cap(tmp_path):
    _write_capture(tmp_path / "A" / "conn.log.labeled", _SAMPLE)
    _write_capture(tmp_path / "B" / "conn.log.labeled", _SAMPLE)
    loader = IoT23Loader()
    df, _ = loader.load(tmp_path, "label", per_file_cap=2)
    assert len(df) == 4                                    # 2 captures × 2 rows each


def test_load_raises_when_no_files(tmp_path):
    (tmp_path / "empty").mkdir()
    loader = IoT23Loader()
    try:
        loader.load(tmp_path, "label")
    except FileNotFoundError as exc:
        assert "no files matching" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_load_custom_glob(tmp_path):
    # Use a non-default glob to test the override path.
    _write_capture(tmp_path / "x.zeek", _SAMPLE)
    loader = IoT23Loader()
    df, _ = loader.load(tmp_path, "label", glob="*.zeek")
    assert len(df) == 3


# ---------- IoT23Downloader ------------------------------------------------

def test_downloader_class_attributes():
    """The downloader's URL/format/landing_url/licence_note are public
    contracts surfaced in profile READMEs and CLI output. Pin them.
    """
    assert IoT23Downloader.url.endswith(".tar.gz")
    assert "stratosphere" in IoT23Downloader.url.lower() or "felk.cvut" in IoT23Downloader.url.lower()
    assert IoT23Downloader.archive_format == "tar.gz"
    assert IoT23Downloader.is_supported is True
    assert "stratosphereips" in IoT23Downloader.landing_url
    assert "CC-BY" in IoT23Downloader.licence_note


def test_downloader_idempotent_on_populated_cache(tmp_path, monkeypatch):
    """If the cache already has data, the underlying downloader hits a
    fast cache-hit path before any network call. We monkey-patch the
    network helper so any unintended fetch would crash, then run.
    """
    # Pre-populate the cache with a non-empty file
    (tmp_path / "already.csv").write_text("x\n1\n")

    # Patch via the canonical module path so the import statement inside
    # `_base.downloader` re-routes to our stub on next call.
    import tabprep.core.downloader as core_dl

    captured: list[tuple] = []

    def fake_stream(url, dest):
        # If the cache is hit, download_and_extract returns BEFORE
        # calling _stream_download — so this should never run.
        captured.append((url, str(dest)))
        return ""

    monkeypatch.setattr(core_dl, "_stream_download", fake_stream)
    IoT23Downloader().download(tmp_path)
    # Cache hit detected — _stream_download must never have been called.
    assert captured == []
