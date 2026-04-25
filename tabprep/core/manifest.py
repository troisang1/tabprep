"""Output manifest: a JSON sidecar describing what was produced and its
SHA-256 hashes. Lets a downstream consumer (or `tabprep verify`) check
that the local outputs match the canonical bytes the profile promises.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tabprep import __version__ as TABPREP_VERSION
from tabprep.core.hashing import canonical_sha256_of_file


@dataclass
class FileEntry:
    path: str
    sha256: str
    rows: int
    cols: int
    bytes: int


@dataclass
class Manifest:
    profile_name: str
    profile_version: str
    profile_path: str
    tabprep_version: str = TABPREP_VERSION
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    files: list[FileEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "profile_version": self.profile_version,
            "profile_path": self.profile_path,
            "tabprep_version": self.tabprep_version,
            "generated_at": self.generated_at,
            "files": [asdict(f) for f in self.files],
        }


def build_manifest(profile_name: str, profile_version: str, profile_path: Path,
                   files: list[Path], shapes: dict[Path, tuple[int, int]]) -> Manifest:
    entries: list[FileEntry] = []
    for f in files:
        rows, cols = shapes.get(f, (-1, -1))
        entries.append(
            FileEntry(
                path=f.name,
                sha256=canonical_sha256_of_file(f),
                rows=int(rows),
                cols=int(cols),
                bytes=f.stat().st_size,
            )
        )
    return Manifest(
        profile_name=profile_name,
        profile_version=profile_version,
        profile_path=str(profile_path),
        files=entries,
    )


def write_manifest(manifest: Manifest, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest.to_dict(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return out_path
