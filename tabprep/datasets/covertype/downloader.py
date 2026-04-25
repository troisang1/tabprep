"""Covertype downloader: pre-fetches Forest Cover Type via sklearn.

`sklearn.datasets.fetch_covtype` caches under `~/scikit_learn_data/`,
so `download(dest_dir)` warms that cache (network call) and writes a
`_complete` marker into `dest_dir` so subsequent runs short-circuit.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from tabprep.datasets._base import BaseDownloader, downloader


@downloader("covertype")
class CovertypeDownloader(BaseDownloader):
    """Pre-fetch the covertype dataset via sklearn.

    Profile usage:
        downloader: covertype
        cached_at: raw/covertype/
    """

    is_supported: ClassVar[bool] = True
    landing_url: ClassVar[str] = (
        "https://archive.ics.uci.edu/dataset/31/covertype"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 (UCI ML Repository — Forest Cover Type, Blackard 1998)"
    )

    SENTINEL: ClassVar[str] = "_complete"

    def download(self, dest_dir: Path) -> None:
        dest = Path(dest_dir)
        marker = dest / self.SENTINEL
        if marker.is_file():
            return  # cache hit — sklearn already has the bytes

        from sklearn.datasets import fetch_covtype

        # Network call — populates ~/scikit_learn_data/.
        # Older sklearn versions don't accept as_frame; fall back.
        try:
            fetch_covtype(as_frame=True)
        except TypeError:
            fetch_covtype()

        dest.mkdir(parents=True, exist_ok=True)
        marker.write_text("covertype\n", encoding="utf-8")
