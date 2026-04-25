"""InSDN dataset package — Software-Defined Networking IDS (Elsayed et al., 2020).

Importing this package registers `InSDNLoader` (`@loader("insdn")`)
and `InSDNDownloader` (`@downloader("insdn")`).
"""
from tabprep.datasets.insdn.downloader import InSDNDownloader  # noqa: F401
from tabprep.datasets.insdn.loader import InSDNLoader  # noqa: F401
