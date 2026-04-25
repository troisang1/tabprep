"""OpenML dataset family — pendigits, letter, optdigits, satimage,
segment, texture, har.

All seven UCI tabular datasets in this family share the same upstream
(`sklearn.datasets.fetch_openml`) and the same `Bunch.data + Bunch.target`
shape, so they're served by a single `(downloader, loader)` pair. Each
profile selects its dataset via `loader_options.openml_name`.

Importing this package registers `OpenMLLoader` (`@loader("openml")`) and
`OpenMLDownloader` (`@downloader("openml")`).
"""
from tabprep.datasets.openml.downloader import OpenMLDownloader  # noqa: F401
from tabprep.datasets.openml.loader import OpenMLLoader  # noqa: F401
