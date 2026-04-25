"""Base abstractions for dataset packages.

Re-exports the public API used by every `tabprep/datasets/<name>/` folder:

    from tabprep.datasets._base import (
        BaseLoader, BaseDownloader,
        HTTPArchiveDownloader, HTTPMultiURLDownloader, FormGatedDownloader,
        loader, downloader,
        LOADER_REGISTRY, DOWNLOADER_REGISTRY,
    )
"""
from tabprep.datasets._base.downloader import (
    BaseDownloader,
    FormGatedDownloader,
    HTTPArchiveDownloader,
    HTTPMultiURLDownloader,
)
from tabprep.datasets._base.loader import BaseLoader
from tabprep.datasets._base._registry import (
    DOWNLOADER_REGISTRY,
    LOADER_REGISTRY,
    downloader,
    loader,
)

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
