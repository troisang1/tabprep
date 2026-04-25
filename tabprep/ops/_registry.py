"""Decorator-based op registry."""
from __future__ import annotations

from typing import Callable, Dict

import pandas as pd

OpFn = Callable[..., pd.DataFrame]
OP_REGISTRY: Dict[str, OpFn] = {}


def op(name: str) -> Callable[[OpFn], OpFn]:
    """Register a callable as a pipeline op under `name`."""

    def deco(fn: OpFn) -> OpFn:
        if name in OP_REGISTRY:
            raise RuntimeError(f"duplicate op registration: {name!r}")
        OP_REGISTRY[name] = fn
        return fn

    return deco
