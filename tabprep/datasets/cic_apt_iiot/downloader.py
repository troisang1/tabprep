"""CIC-APT-IIoT-2024 downloader: form-gated UNB CIC distribution.

UNB CIC restructured its dataset hosting in 2025: the IP-based mirror
at `cicresearch.ca` / `205.174.165.80` no longer serves direct
download URLs (every request now redirects to the landing index page).
Datasets are gated behind a per-request form that emails the
researcher a one-time download token.

Auto-fetching is therefore not feasible for this profile. The user
must visit the landing page below, fill out the request form, and
place the resulting bundle under `cached_at/` manually before running
`tabprep prepare --profile cic_apt_iiot`.

If a future CIC release moves to a scriptable mirror, swap this
class for an `HTTPArchiveDownloader` with the new URL.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import FormGatedDownloader, downloader


@downloader("cic_apt_iiot")
class CICAPTIIoTDownloader(FormGatedDownloader):
    is_supported: ClassVar[bool] = False
    landing_url: ClassVar[str] = (
        "https://www.unb.ca/cic/datasets/iiot-dataset-2024.html"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — UNB CIC request form required (returns a one-time "
        "download token by email). Please cite the UNB CIC paper."
    )
