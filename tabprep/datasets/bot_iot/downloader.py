"""Bot-IoT downloader: Kaggle public mirror (5%-data subset).

Bot-IoT (Koroniotis, Moustafa, Sitnikova, Turnbull, 2018) is one of
the most-cited IoT NIDS datasets. UNSW originally distributed it via
AARNet Cloudstor (decommissioned in 2023) and via SharePoint folder
URLs which return HTTP 403 to non-browser clients (session-bound).

This profile uses the Kaggle public mirror
`vigneshvenkateswaran/bot-iot-5-data` — the canonical 5% subset
(reduced_data_1.csv through reduced_data_4.csv, ~1 GB extracted from
57 MB ZIP). Full 46-column schema including `attack`, `category`,
`subcategory` labels — strictly more useful than the OpenML
10-best-features mirror this previously used.

OpenML id 42072 (`bot-iot-all-features`) is also a valid alternative
when Kaggle is down, but it ships only the 10-best-features
projection. Switching downloaders is a one-line change.

Kaggle's `/api/v1/datasets/download/<owner>/<slug>` endpoint serves
CC-BY public datasets without authentication. HEAD returns 404
(Kaggle quirk); GET returns 200 + `application/zip`. The framework's
`_stream_download` uses GET, so this works.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("bot_iot")
class BotIoTDownloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "vigneshvenkateswaran/bot-iot-5-data"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = (
        "https://research.unsw.edu.au/projects/bot-iot-dataset"
    )
    licence_note: ClassVar[str] = (
        "Research-use only — UNSW academic licence; Kaggle public mirror "
        "of the 5% Bot-IoT subset; please cite Koroniotis et al. (2018)."
    )
