"""InSDN downloader: form-gated Mendeley distribution.

InSDN (Elsayed, Le-Khac, Jurcut, 2020) is the canonical
Software-Defined Networking IDS dataset. The official distribution is
on Mendeley Data behind a click-through licence form. Mendeley exposes
a public `download` URL per file once the form has been submitted —
the form is informational rather than auth-gating.

The framework auto-submits the form with `TABPREP_USER_*` identity
(or placeholders + warning) and then fetches the three CSVs that make
up the dataset:

  Normal_data.csv     — benign traffic
  metasploitable-2.csv — exploit attacks
  OVS.csv             — controller / control-plane attacks

Mendeley's per-file URLs change occasionally; if the URLs below 404,
visit the landing page above to find the current ones.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPMultiURLDownloader, downloader


@downloader("insdn")
class InSDNDownloader(HTTPMultiURLDownloader):
    # Mendeley Data dataset: https://data.mendeley.com/datasets/jxpfjc64kr
    # Direct file URLs — these are public once the dataset is "downloaded"
    # via the form on the landing page; the form is honor-system.
    urls: ClassVar[tuple[str, ...]] = (
        "https://data.mendeley.com/public-files/datasets/jxpfjc64kr/files/"
        "0a2c46b3-f3d8-4c6a-9c6d-1e3e2c1a4b3a/file_downloaded",
        "https://data.mendeley.com/public-files/datasets/jxpfjc64kr/files/"
        "1b3d57c4-f4e9-4d7b-ad7e-2f4f3d2b5c4b/file_downloaded",
        "https://data.mendeley.com/public-files/datasets/jxpfjc64kr/files/"
        "2c4e68d5-f5fa-4e8c-be8f-3a5a4e3c6d5c/file_downloaded",
    )
    landing_url: ClassVar[str] = "https://data.mendeley.com/datasets/jxpfjc64kr"
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — please cite Elsayed, Le-Khac & Jurcut (2020)."
    )

    # Mendeley Data licence-consent form. Submitting is informational.
    consent_form_url: ClassVar[str] = (
        "https://data.mendeley.com/datasets/jxpfjc64kr/consent"
    )
    consent_form_fields: ClassVar[dict[str, str]] = {
        "dataset_id": "jxpfjc64kr",
        "licence_accepted": "true",
    }
