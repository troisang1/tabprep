"""IoT-23 downloader: fetches the Stratosphere Lab lite tarball.

The lite distribution (~9.4 GB) contains only Zeek `conn.log.labeled`
files — no PCAPs — so it's the right starting point for tabprep:
flow-level features only, ~325M total flows across 23 captures.

Download URL is the canonical Stratosphere mirror. License is
CC-BY 4.0 (same as the rest of the Stratosphere IPS dataset
collection); no form, no auth, fully scriptable.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("iot23")
class IoT23Downloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/"
        "iot_23_datasets_small.tar.gz"
    )
    archive_format: ClassVar[str] = "tar.gz"
    landing_url: ClassVar[str] = "https://www.stratosphereips.org/datasets-iot23"
    licence_note: ClassVar[str] = "CC-BY 4.0"
    # Upstream does not publish a SHA-256 for the lite tarball. If a
    # future release pins one, set `sha256` here to enable the
    # download-time integrity check in HTTPArchiveDownloader.
    # sha256: ClassVar[str] = "..."
