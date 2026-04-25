"""NSL-KDD downloader: fetches the cleaned-up KDD-99 archive.

NSL-KDD (Tavallaee, Bagheri, Lu & Ghorbani, 2009) removed the duplicate
records that plagued the original KDD-99 distribution. It's the
de-facto legacy IDS baseline, still widely cited despite being
captured in 1998. Five files in the standard distribution:

  KDDTrain+.txt          — full training set with labels (~125k rows)
  KDDTrain+_20Percent.txt — 20% subsample (~25k)
  KDDTest+.txt           — full test set (~22k)
  KDDTest-21.txt         — test rows that 21+ KDD-99 classifiers got wrong
  KDDTrain+.arff         — ARFF version (skipped here — we use the .txt)

The UNB CIC mirror serves a single ZIP at the URL pinned below. No
licence form is required for this specific dataset.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("nsl_kdd")
class NSLKDDDownloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "http://205.174.165.80/CICDataset/NSL-KDD/Dataset/NSL-KDD.zip"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = "https://www.unb.ca/cic/datasets/nsl.html"
    licence_note: ClassVar[str] = (
        "Open access (UNB CIC mirror); please cite Tavallaee et al. 2009"
    )
