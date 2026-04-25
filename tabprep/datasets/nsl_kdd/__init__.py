"""NSL-KDD dataset package — cleaned-up KDD-99 (Tavallaee et al., 2009).

Importing this package registers `NSLKDDLoader` (`@loader("nsl_kdd")`)
and `NSLKDDDownloader` (`@downloader("nsl_kdd")`).
"""
from tabprep.datasets.nsl_kdd.downloader import NSLKDDDownloader  # noqa: F401
from tabprep.datasets.nsl_kdd.loader import NSLKDDLoader  # noqa: F401
