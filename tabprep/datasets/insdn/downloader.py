"""InSDN downloader: form-gated Mendeley distribution.

InSDN (Elsayed, Le-Khac, Jurcut, 2020) is the canonical
Software-Defined Networking IDS dataset. Mendeley Data hosts the
files under a per-session JS-presigned URL pattern — the file UUIDs
on the public download endpoints rotate per browser session, so
direct HTTP fetching by URL isn't reliable.

The user has two manual paths:

1. Visit the landing page below, accept the CC-BY 4.0 licence, click
   "Download All", and place the resulting zip under `cached_at/`.
2. Use the Kaggle mirror (`badcodebuilder/insdn-dataset`) if you have
   Kaggle API credentials configured.

Either way, prefer letting the user populate `cached_at/` themselves
rather than trying to scrape Mendeley's JS-rendered page.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import FormGatedDownloader, downloader


@downloader("insdn")
class InSDNDownloader(FormGatedDownloader):
    is_supported: ClassVar[bool] = False
    landing_url: ClassVar[str] = (
        "https://data.mendeley.com/datasets/jxpfjc64kr/1"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — Mendeley per-session URLs (JS-rendered); please "
        "cite Elsayed, Le-Khac & Jurcut (2020)."
    )
