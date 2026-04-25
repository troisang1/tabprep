"""InSDN downloader: Kaggle public-mirror auto-fetch.

InSDN (Elsayed, Le-Khac, Jurcut, 2020) was originally distributed on
Mendeley Data with JS-presigned URLs that rotate per session — making
direct HTTP fetching unreliable. The Kaggle public mirror
`badcodebuilder/insdn-dataset` carries the same three CSVs
(`Normal_data.csv`, `metasploitable-2.csv`, `OVS.csv`) under
`InSDN_DatasetCSV/` and is auto-fetchable without auth (Kaggle's
`/api/v1/datasets/download/` endpoint serves CC-BY datasets to
unauthenticated GET requests).

The fetched ZIP is ~22 MB; the loader walks recursively for `*.csv`
so the `InSDN_DatasetCSV/` prefix is handled transparently.

Kaggle quirk: `curl -I` (HEAD) returns 404, but `curl` (GET) returns
HTTP 200 + `application/zip`. The framework's `_stream_download`
uses GET, so this works.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("insdn")
class InSDNDownloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "https://www.kaggle.com/api/v1/datasets/download/badcodebuilder/insdn-dataset"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = (
        "https://data.mendeley.com/datasets/jxpfjc64kr/1"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — Kaggle mirror of the Mendeley distribution; please "
        "cite Elsayed, Le-Khac & Jurcut (2020)."
    )
