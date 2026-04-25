"""NSL-KDD downloader: fetches via the public GitHub mirror.

NSL-KDD (Tavallaee, Bagheri, Lu & Ghorbani, 2009) removed the duplicate
records that plagued the original KDD-99 distribution. It's the
de-facto legacy IDS baseline, still widely cited despite being
captured in 1998. Four canonical text files:

  KDDTrain+.txt          — full training set with labels (~125k rows)
  KDDTrain+_20Percent.txt — 20% subsample (~25k)
  KDDTest+.txt           — full test set (~22k)
  KDDTest-21.txt         — test rows that 21+ KDD-99 classifiers got wrong

Originally distributed via UNB CIC's IP-based mirror, which has been
locked down post-2025 (every direct download URL now redirects to the
landing page index). The well-maintained GitHub mirror at
`defcom17/NSL_KDD` serves the same plain-text files at stable raw
URLs and is the de-facto canonical source as of 2026.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPMultiURLDownloader, downloader


@downloader("nsl_kdd")
class NSLKDDDownloader(HTTPMultiURLDownloader):
    urls: ClassVar[tuple[str, ...]] = (
        "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain%2B.txt",
        "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain%2B_20Percent.txt",
        "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest%2B.txt",
        "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTest-21.txt",
    )
    landing_url: ClassVar[str] = "https://github.com/defcom17/NSL_KDD"
    licence_note: ClassVar[str] = (
        "Open access (GitHub mirror); please cite Tavallaee et al. 2009"
    )
