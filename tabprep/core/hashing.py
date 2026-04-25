"""SHA-256 helpers — used both for source-file integrity and for verifying
the byte-stable output CSVs against a profile's `expected_hashes`."""
from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1 << 20  # 1 MiB


def sha256_of_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest of an arbitrary file's bytes."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# An alias to make the intent explicit at call sites: the file we are
# hashing is supposed to be the result of a *canonical* write (deterministic
# byte-for-byte format), not just any CSV.
canonical_sha256_of_file = sha256_of_file
