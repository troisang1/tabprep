"""Decorator-based registries for dataset loaders and downloaders.

Each dataset under `tabprep/datasets/<name>/` registers its loader and
downloader classes via:

    from tabprep.datasets._base import BaseLoader, loader
    @loader("iot23")
    class IoT23Loader(BaseLoader): ...

    from tabprep.datasets._base import HTTPArchiveDownloader, downloader
    @downloader("iot23")
    class IoT23Downloader(HTTPArchiveDownloader):
        url = "https://..."

The framework's pipeline looks up the registered class by name from
the profile YAML's `loader:` / `downloader:` keys.
"""
from __future__ import annotations

from typing import Type

from tabprep.datasets._base.downloader import BaseDownloader
from tabprep.datasets._base.loader import BaseLoader

LOADER_REGISTRY: dict[str, Type[BaseLoader]] = {}
DOWNLOADER_REGISTRY: dict[str, Type[BaseDownloader]] = {}


def loader(name: str):
    """Register a `BaseLoader` subclass under `name`."""
    def deco(cls: Type[BaseLoader]) -> Type[BaseLoader]:
        if not issubclass(cls, BaseLoader):
            raise TypeError(f"@loader({name!r}): {cls.__name__} must subclass BaseLoader")
        if name in LOADER_REGISTRY:
            raise RuntimeError(f"duplicate loader registration: {name!r}")
        LOADER_REGISTRY[name] = cls
        return cls
    return deco


def downloader(name: str):
    """Register a `BaseDownloader` subclass under `name`."""
    def deco(cls: Type[BaseDownloader]) -> Type[BaseDownloader]:
        if not issubclass(cls, BaseDownloader):
            raise TypeError(f"@downloader({name!r}): {cls.__name__} must subclass BaseDownloader")
        if name in DOWNLOADER_REGISTRY:
            raise RuntimeError(f"duplicate downloader registration: {name!r}")
        DOWNLOADER_REGISTRY[name] = cls
        return cls
    return deco
