"""UNSW-NB15 downloader: Zenodo public mirror of the four numbered CSVs.

The original UNSW-NB15 distribution (Moustafa & Slay 2015) was hosted
on UNSW Canberra's research portal and is now mirrored on Zenodo
(record 10140548). The Zenodo record carries four CSVs totalling
~588 MB plus the ground-truth `UNSW-NB15_GT.csv` and feature schema
file. This downloader fetches only the four numbered network-flow
CSVs that the loader concatenates.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPMultiURLDownloader, downloader


@downloader("unsw_nb15")
class UNSWNB15Downloader(HTTPMultiURLDownloader):
    urls: ClassVar[tuple[str, ...]] = (
        "https://zenodo.org/api/records/10140548/files/UNSW-NB15_1.csv/content",
        "https://zenodo.org/api/records/10140548/files/UNSW-NB15_2.csv/content",
        "https://zenodo.org/api/records/10140548/files/UNSW-NB15_3.csv/content",
        "https://zenodo.org/api/records/10140548/files/UNSW-NB15_4.csv/content",
    )
    archive_format: ClassVar[str | None] = None        # CSVs are uncompressed
    landing_url: ClassVar[str] = "https://zenodo.org/records/10140548"
    licence_note: ClassVar[str] = (
        "UNSW-NB15 — academic redistribution via Zenodo; please cite "
        "Moustafa & Slay (MilCIS 2015)."
    )
