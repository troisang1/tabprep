"""Covertype dataset package — Forest cover type (Statlog).

Standalone (not part of the `openml/` family) because
`sklearn.datasets.fetch_covtype` has a different signature than
`fetch_openml` (no per-name argument, occasionally returns ndarray
output instead of `Bunch.data` on older sklearn versions).

Importing this package registers `CovertypeLoader` (`@loader("covertype")`)
and `CovertypeDownloader` (`@downloader("covertype")`).
"""
from tabprep.datasets.covertype.downloader import CovertypeDownloader  # noqa: F401
from tabprep.datasets.covertype.loader import CovertypeLoader  # noqa: F401
