"""`BaseDownloader` — abstract base for dataset downloaders.

A downloader fetches the raw bytes for a dataset into a local
`cached_at` directory. Concrete subclasses live under
`tabprep/datasets/<name>/downloader.py` and register themselves with
`@downloader("name")`.

The base class provides:

  * `download(dest_dir)` — abstract, must be overridden;
  * `is_cache_populated(dest_dir)` — default idempotency check (any
    non-empty file under `dest_dir`); override if your dataset has a
    more specific completeness criterion (e.g. presence of a sentinel
    `_complete` marker file);
  * `refusal_message()` — human-readable explanation for form-gated
    datasets that we do **not** auto-download (CIC, IEEE DataPort,
    UNSW SharePoint, Mendeley JS-presigned). Used by the CLI to
    surface a friendly hint when `download()` is called on a profile
    whose `is_supported = False`.

Two well-known concrete subclasses live in the framework:
  * `tabprep.datasets._base.HTTPArchiveDownloader` — generic single-URL
    fetch + extract (tar.gz / zip / gz / single file). Used by IoT-23,
    UCI archive, etc.
  * `tabprep.datasets._base.FormGatedDownloader` — polite refusal
    that prints `landing_url` for the user to visit. Used by CIC
    family, 5G-NIDD (IEEE DataPort), Edge-IIoTSet (Mendeley), etc.

Each dataset's downloader can also subclass these convenience classes
directly when the default behaviour fits.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from tabprep.core.downloader import (
    _has_data,
    download_and_extract,
    derive_target_name,
)


class BaseDownloader(ABC):
    """Abstract base. Subclasses implement `download(dest_dir)`."""

    # --- class-level metadata that subclasses set -------------------------

    is_supported: ClassVar[bool] = True
    """Whether this downloader can actually fetch bytes. False marks a
    polite-refusal subclass for form-gated upstreams (CIC, etc.)."""

    landing_url: ClassVar[str] = ""
    """Human-facing landing page where the licence form lives. Surfaced
    in the refusal message for form-gated downloaders."""

    licence_note: ClassVar[str] = ""
    """One-line summary of the dataset's licence (e.g. "CC-BY 4.0",
    "Research use only — UNSW academic licence"). Optional."""

    # --- the contract ----------------------------------------------------

    @abstractmethod
    def download(self, dest_dir: Path) -> None:
        """Fetch raw data into `dest_dir`. Idempotent: skip if data
        already present, raise if a precondition fails (network down,
        upstream URL changed, checksum mismatch).
        """
        ...

    # --- shared helpers --------------------------------------------------

    def is_cache_populated(self, dest_dir: Path) -> bool:
        """Default: any non-empty file under `dest_dir` is a cache hit.

        Override this if your dataset has a more specific completeness
        criterion (e.g. presence of all expected sub-directories).
        """
        return _has_data(Path(dest_dir))

    def refusal_message(self) -> str:
        """Surface this when the user calls a form-gated downloader."""
        url = self.landing_url or "<see profile description>"
        return (
            f"This dataset cannot be auto-downloaded "
            f"({self.licence_note or 'upstream is form/JS-gated'}).\n"
            f"  Visit:  {url}\n"
            f"  Complete the licence form, then place the raw data under "
            f"the profile's `cached_at:` path and re-run `tabprep prepare`."
        )


# ---------------------------------------------------------------------------
# Concrete convenience subclasses
# ---------------------------------------------------------------------------

class HTTPArchiveDownloader(BaseDownloader):
    """Generic single-URL fetch + (optional) archive extract.

    Subclasses set the class attributes:

        url: str                 # required
        sha256: str | None       # optional integrity check
        archive_format: str | None
                                 # tar.gz | tgz | tar | zip | gz | none
                                 # None → auto-detect from the URL suffix

    Useful for IoT-23, UCI archive, Zenodo direct downloads, etc.
    """

    url: ClassVar[str] = ""
    sha256: ClassVar[str | None] = None
    archive_format: ClassVar[str | None] = None

    def download(self, dest_dir: Path) -> None:
        if not self.url:
            raise RuntimeError(
                f"{type(self).__name__}: subclass must set `url` class attribute"
            )
        download_and_extract(
            self.url,
            Path(dest_dir),
            archive_format=self.archive_format,
            expected_sha256=self.sha256,
        )


class HTTPMultiURLDownloader(BaseDownloader):
    """Multi-URL variant for datasets that ship as several stand-alone
    files at distinct URLs (e.g. UNSW-NB15's four numbered CSVs on
    Zenodo).

    Subclasses set:

        urls: list[str]          # required, fetched in order
        archive_format: str | None  # applied uniformly to every URL
    """

    urls: ClassVar[tuple[str, ...]] = ()
    archive_format: ClassVar[str | None] = None

    def download(self, dest_dir: Path) -> None:
        if not self.urls:
            raise RuntimeError(
                f"{type(self).__name__}: subclass must set `urls` class attribute"
            )
        cached = Path(dest_dir)
        for u in self.urls:
            target = derive_target_name(u)
            download_and_extract(
                u,
                cached,
                archive_format=self.archive_format,
                target_name=target,
            )


class FormGatedDownloader(BaseDownloader):
    """Polite-refusal downloader for upstreams that gate access behind
    a licence form, JS-signed S3 URLs, or interactive auth.

    Subclasses just set `landing_url` and `licence_note`. Calling
    `download()` raises with a clear hint for the user.
    """

    is_supported: ClassVar[bool] = False

    def download(self, dest_dir: Path) -> None:
        raise RuntimeError(self.refusal_message())
