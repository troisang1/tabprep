"""Pipeline ops registry.

Each op is a small pure function with the signature
    fn(df: pd.DataFrame, *, label_col: str, **params) -> pd.DataFrame

decorated with `@op("name")` so it can be referenced from a profile YAML
by string. New ops can be added without touching the executor — they
register themselves at import time.
"""
from tabprep.ops._registry import OP_REGISTRY, op  # noqa: F401

# Importing the modules below populates OP_REGISTRY via @op side effects.
from tabprep.ops import clean, encode, filter, label, sample  # noqa: F401, E402

__all__ = ["OP_REGISTRY", "op"]
