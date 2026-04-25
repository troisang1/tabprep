"""CIC-IoMT-2024 downloader: Kaggle mirror (attacks ZIP).

UNB CIC's official URLs were locked down in 2025; the Kaggle mirror
`zeynepdemirta/ciciomt2024-attacks` carries the labelled attack
distribution as a ZIP of per-pcap CSVs under `csv/test/` and
`csv/train/`. Total ~281 MB.

A separate "profilling" ZIP exists (~34 MB of benign device traffic
under `profilling_CSV/`); this profile uses only the attacks ZIP
because the attacks ZIP already carries `Benign_test.pcap.csv` and
`Benign_train.pcap.csv`. Adding the profiling subset would scatter
benign labels across many small per-device classes that the
`filter_min_class_count` step drops anyway.

Kaggle's `/api/v1/datasets/download/<owner>/<slug>` endpoint serves
CC-BY datasets without authentication (HEAD returns 404, GET returns
200 — framework uses GET via `_stream_download`).
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("cic_iomt2024")
class CICIoMT2024Downloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "https://www.kaggle.com/api/v1/datasets/download/"
        "zeynepdemirta/ciciomt2024-attacks"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = (
        "https://www.unb.ca/cic/datasets/iomt-dataset-2024.html"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — Kaggle mirror of UNB CIC's 2024 IoMT release; "
        "please cite the UNB CIC paper."
    )
