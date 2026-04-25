"""Source loader: HTTP(S) URL with optional checksum verification."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.hashing import sha256_of_file
from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source


@source("url")
def load_url(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    """Read a CSV from `cached_at` (relative to repo root). If the file is
    not present and `url` is set, the user is told to download it. We do
    not silently auto-download — many IDS dataset sources require login
    or rate-limit; explicit user action is safer.
    """
    if not spec.cached_at:
        raise ValueError("url source: profile.source.cached_at is required "
                         "(relative path under data/raw/...)")
    cached = Path(spec.cached_at).expanduser()
    if not cached.is_absolute():
        # Resolve relative to the current working dir (the user typically
        # runs `tabprep prepare ...` from the cnNFST repo root).
        cached = Path.cwd() / cached
    if not cached.is_file():
        raise FileNotFoundError(
            f"url source: file not found at {cached}.\n"
            f"  Download the dataset from {spec.url or '<url>'} and place "
            f"it at: {spec.cached_at}\n"
        )

    if spec.sha256:
        observed = sha256_of_file(cached)
        if observed != spec.sha256:
            raise RuntimeError(
                f"url source: checksum mismatch on {cached}\n"
                f"  expected sha256: {spec.sha256}\n"
                f"  observed sha256: {observed}\n"
                f"  the upstream file may have changed; update the profile "
                f"or re-download."
            )

    df = pd.read_csv(cached, low_memory=False)
    return df, label
