"""UNSW-NB15 dataset package — Moustafa & Slay (2015) IDS distribution.

Importing this package registers `UNSWNB15Loader` (`@loader("unsw_nb15")`)
and `UNSWNB15Downloader` (`@downloader("unsw_nb15")`).
"""
from tabprep.datasets.unsw_nb15.downloader import UNSWNB15Downloader  # noqa: F401
from tabprep.datasets.unsw_nb15.loader import UNSWNB15Loader  # noqa: F401
