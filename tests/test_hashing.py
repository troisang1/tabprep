"""Unit tests for `tabprep/core/hashing.py`."""
from __future__ import annotations

import hashlib

from tabprep.core.hashing import canonical_sha256_of_file, sha256_of_file


def test_sha256_of_empty_file(tmp_path):
    p = tmp_path / "empty.bin"
    p.write_bytes(b"")
    expected = hashlib.sha256(b"").hexdigest()
    assert sha256_of_file(p) == expected


def test_sha256_of_known_content(tmp_path):
    p = tmp_path / "x.txt"
    content = b"hello, world\n"
    p.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert sha256_of_file(p) == expected


def test_sha256_streams_large_files(tmp_path):
    """The helper streams in 1 MiB chunks; verify it doesn't break with a
    file larger than CHUNK_SIZE."""
    p = tmp_path / "big.bin"
    # 3 MiB of repeating bytes — enough to span multiple chunks.
    content = b"x" * (3 * (1 << 20))
    p.write_bytes(content)
    assert sha256_of_file(p) == hashlib.sha256(content).hexdigest()


def test_canonical_alias_points_at_same_function():
    """`canonical_sha256_of_file` is a documented alias — they must be
    the same callable so the alias never drifts."""
    assert canonical_sha256_of_file is sha256_of_file


def test_sha256_of_file_accepts_string_path(tmp_path):
    p = tmp_path / "x.txt"
    p.write_bytes(b"data")
    by_str = sha256_of_file(str(p))
    by_path = sha256_of_file(p)
    assert by_str == by_path
