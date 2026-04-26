"""CIC-APT-IIoT-2024 downloader: Kaggle public-mirror auto-fetch.

UNB CIC restructured its dataset hosting in 2025: the IP-based mirror
at `cicresearch.ca` / `205.174.165.80` no longer serves direct
download URLs (every request now redirects to the landing index page).
Datasets there are gated behind a per-request form that emails the
researcher a one-time download token — **not** scriptable.

The Kaggle public mirror `waqarkha/cicapt-iiot` carries the same
distribution as a 2.4 GB ZIP containing two phase CSVs
(`phase1_NetworkData.csv` ~5.4 GB and `phase2_NetworkData.csv` ~4.3 GB
uncompressed, total ~9.7 GB extracted). Schema includes the `label`
column the profile expects. Kaggle's `/api/v1/datasets/download/...`
endpoint serves CC-BY datasets without authentication via GET (HEAD
returns 404 — Kaggle quirk; framework uses GET).
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("cic_apt_iiot")
class CICAPTIIoTDownloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "https://www.kaggle.com/api/v1/datasets/download/waqarkha/cicapt-iiot"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = (
        "https://www.unb.ca/cic/datasets/iiot-dataset-2024.html"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — Kaggle mirror of the UNB CIC distribution; please "
        "cite the UNB CIC paper."
    )
