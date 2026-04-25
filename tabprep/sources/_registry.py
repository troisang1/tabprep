"""Source-loader registry."""
from __future__ import annotations

from typing import Callable, Dict, Tuple

import pandas as pd

SourceFn = Callable[..., Tuple[pd.DataFrame, str]]
SOURCE_REGISTRY: Dict[str, SourceFn] = {}


def source(kind: str) -> Callable[[SourceFn], SourceFn]:
    """Register a callable as a source loader for the given `kind`."""

    def deco(fn: SourceFn) -> SourceFn:
        if kind in SOURCE_REGISTRY:
            raise RuntimeError(f"duplicate source registration: {kind!r}")
        SOURCE_REGISTRY[kind] = fn
        return fn

    return deco
