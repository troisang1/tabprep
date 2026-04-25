"""Smoke test for the zeek_conn_log source loader using synthetic input."""
from __future__ import annotations

from pathlib import Path

from tabprep.core.profile import SourceSpec
from tabprep.sources.zeek_conn_log_source import load_zeek_conn_log


# A minimal but realistic Zeek conn.log.labeled fragment matching the
# IoT-23 schema. Tab-separated; metadata lines start with `#`.
_SAMPLE = (
    "#separator \\x09\n"
    "#set_separator\t,\n"
    "#empty_field\t(empty)\n"
    "#unset_field\t-\n"
    "#path\tconn\n"
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p"
    "\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state"
    "\tlabel\tdetailed-label\n"
    "#types\ttime\tstring\taddr\tport\taddr\tport\tenum\tstring\tinterval"
    "\tcount\tcount\tstring\tstring\tstring\n"
    "1545379977.0\tCw7Y\t192.168.1.1\t49259\t10.0.0.1\t23\ttcp\t-"
    "\t-\t-\t-\tS0\tMalicious\tPartOfAHorizontalPortScan\n"
    "1545379980.0\tCxQ8\t192.168.1.1\t49260\t10.0.0.2\t80\ttcp\thttp"
    "\t1.5\t250\t800\tSF\tBenign\t-\n"
    "1545379985.0\tDp1z\t192.168.1.1\t49261\t10.0.0.3\t1900\tudp\t-"
    "\t0.1\t44\t0\tS0\tMalicious\tMirai\n"
)


def _write_capture(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_zeek_loader_parses_fields_header(tmp_path):
    _write_capture(tmp_path / "captureA" / "conn.log.labeled", _SAMPLE)
    spec = SourceSpec(kind="zeek_conn_log", cached_at=str(tmp_path))
    df, label = load_zeek_conn_log(spec, label="label")
    assert label == "label"
    # Columns parsed from `#fields` header
    assert "ts" in df.columns
    assert "id.orig_h" in df.columns
    assert "detailed-label" in df.columns
    # Metadata lines are skipped, all 3 data rows present
    assert len(df) == 3
    # Values are populated; the "-" sentinel is parsed as NaN
    assert df.loc[0, "id.orig_h"] == "192.168.1.1"
    assert df.loc[0, "service"] != df.loc[0, "service"]   # NaN != NaN
    assert df.loc[1, "service"] == "http"


def test_zeek_loader_concatenates_multiple_captures(tmp_path):
    _write_capture(tmp_path / "captureA" / "conn.log.labeled", _SAMPLE)
    _write_capture(tmp_path / "captureB" / "conn.log.labeled", _SAMPLE)
    spec = SourceSpec(kind="zeek_conn_log", cached_at=str(tmp_path))
    df, _ = load_zeek_conn_log(spec, label="label")
    assert len(df) == 6                                    # 3 rows × 2 captures


def test_zeek_loader_raises_when_no_files(tmp_path):
    (tmp_path / "empty").mkdir()
    spec = SourceSpec(kind="zeek_conn_log", cached_at=str(tmp_path))
    try:
        load_zeek_conn_log(spec, label="label")
    except FileNotFoundError as exc:
        assert "no files matching" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError when directory is empty")
