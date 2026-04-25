"""OpenML downloader: pre-fetches an OpenML dataset via sklearn.

`sklearn.datasets.fetch_openml` caches under `~/scikit_learn_data/`, so
`download(dest_dir)` warms that cache (network call) and writes a small
`_complete` marker into `dest_dir`. On subsequent runs the marker check
short-circuits before any network call. The marker contains the dataset
name (non-empty) so the inherited `is_cache_populated()` would also
report a cache hit if any future caller relies on it.

The OpenML name is conveyed through the tail directory of `dest_dir`
(`raw/openml/pendigits/` → `pendigits`). This is the same string the
profile passes to the loader via `loader_options.openml_name`, so the
two stay in sync without threading extra context through the registry
contract (which only knows class names, not per-profile state).

Caveat: this downloader hard-codes `version=1` because the framework
contract doesn't pass `loader_options` to downloaders. Profiles that
pin a non-default `openml_version` will still work — the loader is the
source of truth — but pre-fetching wastes one extra network round-trip
in that edge case. All seven currently shipped OpenML profiles use
`openml_version: 1`.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from tabprep.datasets._base import BaseDownloader, downloader


@downloader("openml")
class OpenMLDownloader(BaseDownloader):
    """Pre-fetch an OpenML dataset via sklearn.

    Profile usage:
        downloader: openml
        cached_at: raw/openml/<openml_name>/
        loader_options:
          openml_name: <openml_name>
          openml_version: 1
    """

    is_supported: ClassVar[bool] = True
    landing_url: ClassVar[str] = "https://www.openml.org/"
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 (per-dataset; verify on the OpenML page)"
    )

    DEFAULT_VERSION: ClassVar[int] = 1
    """OpenML datasets are versioned. v1 is the canonical UCI mirror for
    the seven datasets we ship; override per-profile via
    `loader_options.openml_version` if a future re-pin is needed."""

    SENTINEL: ClassVar[str] = "_complete"
    """Marker file written into `cached_at/` after a successful fetch.
    Skipping the network call on re-run is handled by `download()` itself
    via `marker.is_file()`. The marker is non-empty (contains the dataset
    name) so `is_cache_populated()` — which checks for any non-zero file
    — also reports True on a populated cache."""

    def download(self, dest_dir: Path) -> None:
        dest = Path(dest_dir)
        marker = dest / self.SENTINEL
        if marker.is_file():
            return  # cache hit — sklearn already has the bytes

        name = dest.name
        if not name:
            raise RuntimeError(
                f"OpenMLDownloader: cannot infer dataset name from "
                f"empty cached_at tail (got {dest!r}). Set "
                f"`cached_at: raw/openml/<name>/` in the profile."
            )

        from sklearn.datasets import fetch_openml

        # Network call — populates ~/scikit_learn_data/.
        fetch_openml(name, version=self.DEFAULT_VERSION,
                     as_frame=True, parser="auto")

        dest.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"openml:{name}\n", encoding="utf-8")
