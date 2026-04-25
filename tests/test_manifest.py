"""Unit tests for `tabprep/core/manifest.py`."""
from __future__ import annotations

import json

from tabprep import __version__ as TABPREP_VERSION
from tabprep.core.manifest import (
    FileEntry,
    Manifest,
    build_manifest,
    write_manifest,
)


def test_build_manifest_populates_file_entries(tmp_path):
    f1 = tmp_path / "train.csv"
    f2 = tmp_path / "test.csv"
    f1.write_text("a\n1\n2\n", encoding="utf-8")
    f2.write_text("a\n3\n4\n5\n", encoding="utf-8")

    manifest = build_manifest(
        profile_name="t",
        profile_version="1.0.0",
        profile_path=tmp_path / "p.yaml",
        files=[f1, f2],
        shapes={f1: (2, 1), f2: (3, 1)},
    )

    assert manifest.profile_name == "t"
    assert manifest.profile_version == "1.0.0"
    assert manifest.tabprep_version == TABPREP_VERSION
    assert len(manifest.files) == 2

    entries = {e.path: e for e in manifest.files}
    assert entries["train.csv"].rows == 2
    assert entries["train.csv"].cols == 1
    assert entries["train.csv"].bytes == f1.stat().st_size
    assert entries["train.csv"].sha256                                 # 64 hex chars
    assert len(entries["train.csv"].sha256) == 64
    assert entries["test.csv"].rows == 3


def test_build_manifest_handles_missing_shape_gracefully(tmp_path):
    """If `shapes` dict has no entry for a file, the manifest records
    (-1, -1) so the JSON output stays well-typed."""
    f = tmp_path / "x.csv"
    f.write_text("a\n1\n", encoding="utf-8")
    manifest = build_manifest(
        profile_name="t",
        profile_version="1.0",
        profile_path=tmp_path / "p.yaml",
        files=[f],
        shapes={},
    )
    assert manifest.files[0].rows == -1
    assert manifest.files[0].cols == -1


def test_write_manifest_serialises_deterministic_json(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = build_manifest(
        profile_name="t", profile_version="1.0",
        profile_path=tmp_path / "p.yaml",
        files=[f], shapes={f: (1, 2)},
    )
    out = write_manifest(manifest, tmp_path / "_manifest.json")
    assert out.is_file()

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["profile_name"] == "t"
    assert data["profile_version"] == "1.0"
    assert data["tabprep_version"] == TABPREP_VERSION
    assert "generated_at" in data
    assert isinstance(data["files"], list)
    assert data["files"][0]["path"] == "x.csv"


def test_write_manifest_pretty_prints_with_sorted_keys(tmp_path):
    """`write_manifest` uses indent=2, sort_keys=True. Verify the output
    has a stable key order (alphabetical) so diffs across runs are tight."""
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = build_manifest(
        profile_name="t", profile_version="1.0",
        profile_path=tmp_path / "p.yaml",
        files=[f], shapes={f: (1, 2)},
    )
    out = write_manifest(manifest, tmp_path / "_manifest.json")
    text = out.read_text(encoding="utf-8")
    # Top-level keys should be in sorted order.
    files_idx = text.find('"files"')
    name_idx = text.find('"profile_name"')
    assert files_idx >= 0
    assert name_idx >= 0
    assert files_idx < name_idx        # 'files' < 'profile_name' alphabetically


def test_manifest_to_dict_round_trips_via_json(tmp_path):
    f = tmp_path / "out.csv"
    f.write_text("hi\n", encoding="utf-8")
    m = build_manifest(
        profile_name="t", profile_version="0.1",
        profile_path=tmp_path / "p.yaml",
        files=[f], shapes={f: (0, 1)},
    )
    blob = json.dumps(m.to_dict())
    parsed = json.loads(blob)
    assert parsed["profile_name"] == "t"
    assert parsed["files"][0]["path"] == "out.csv"


def test_file_entry_dataclass_shape():
    """The FileEntry public fields are part of the manifest schema."""
    e = FileEntry(path="x", sha256="abc", rows=1, cols=2, bytes=10)
    assert e.path == "x"
    assert e.rows == 1
    assert e.cols == 2
    assert e.bytes == 10


def test_manifest_dataclass_default_factory():
    """`generated_at` is filled by default factory; `files` defaults to []."""
    m = Manifest(profile_name="t", profile_version="0", profile_path="p")
    assert m.files == []
    assert m.generated_at                     # ISO8601 string from factory
    assert "T" in m.generated_at              # ISO format includes 'T'
