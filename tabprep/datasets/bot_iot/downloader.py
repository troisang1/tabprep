"""Bot-IoT downloader: UNSW Canberra Cloudstor distribution + consent.

Bot-IoT (Koroniotis, Moustafa, Sitnikova, Turnbull, 2018) is one of
the most cited IoT NIDS datasets. UNSW distributes it through the
AARNet Cloudstor service with a click-through licence at the landing
page. The framework auto-submits a consent form with the user's
identity, then fetches the multi-CSV distribution.

The dataset is large (~16.7 GB unpacked); the upstream provides a
"10-best-features" subsampled version (~70 MB) which is what we ship
by default. Profile authors who want the full archive can override
the URLs.

URL stability: UNSW Cloudstor occasionally re-issues download tokens.
If the URL 404s, visit the landing page above to find the current one
and update `urls` in `tabprep/datasets/bot_iot/downloader.py`.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("bot_iot")
class BotIoTDownloader(HTTPArchiveDownloader):
    # The "10-best-features" subset (70 MB CSV) — small enough to
    # auto-download in CI, popular enough to be the default in most
    # Bot-IoT papers. Override for the full ~16.7 GB distribution.
    url: ClassVar[str] = (
        "https://cloudstor.aarnet.edu.au/plus/s/umT99TnxvbpkkoE/download"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = (
        "https://research.unsw.edu.au/projects/bot-iot-dataset"
    )
    licence_note: ClassVar[str] = (
        "Research-use only — UNSW academic licence; please cite "
        "Koroniotis et al. (2018)."
    )

    # UNSW Bot-IoT licence-acceptance form (Microsoft Forms). The
    # framework auto-submits with TABPREP_USER_* identity.
    consent_form_url: ClassVar[str] = (
        "https://research.unsw.edu.au/projects/bot-iot-dataset/consent"
    )
    consent_form_fields: ClassVar[dict[str, str]] = {
        "dataset": "Bot-IoT",
        "version": "10best",
        "licence_accepted": "true",
    }
