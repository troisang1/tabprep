"""`tabprep.datasets` — per-dataset (or per-source-family) packages.

Each dataset that needs custom download or load logic ships as a
subdirectory under this package, e.g. `tabprep/datasets/iot23/`. Each
folder contains:

  * `__init__.py`     — imports & registers the dataset's classes
  * `downloader.py`   — concrete `BaseDownloader` subclass
  * `loader.py`       — concrete `BaseLoader` subclass
  * `ops.py`          — (optional) dataset-specific pipeline ops
  * `README.md`       — (optional) provenance / known issues

Datasets that share both the upstream source and the file layout
(notably the OpenML family: pendigits, letter, optdigits, …) live in
**one** folder named after that source family.

This package's `__init__.py` walks every immediate subdirectory at
import time and `importlib.import_module(f"{__name__}.{sub}")`. Each
subdir's `@loader` / `@downloader` decorators then populate the
registries in `_base/_registry.py`.
"""
from __future__ import annotations

import importlib
import pkgutil

from tabprep.datasets._base import (  # noqa: F401  (re-export)
    BaseDownloader,
    BaseLoader,
    DOWNLOADER_REGISTRY,
    FormGatedDownloader,
    HTTPArchiveDownloader,
    HTTPMultiURLDownloader,
    LOADER_REGISTRY,
    downloader,
    loader,
)


def _autoload() -> None:
    """Import every immediate sub-package so its decorators run."""
    pkg = __name__
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        importlib.import_module(f"{pkg}.{name}")


_autoload()


__all__ = [
    "BaseLoader",
    "BaseDownloader",
    "HTTPArchiveDownloader",
    "HTTPMultiURLDownloader",
    "FormGatedDownloader",
    "loader",
    "downloader",
    "LOADER_REGISTRY",
    "DOWNLOADER_REGISTRY",
]
