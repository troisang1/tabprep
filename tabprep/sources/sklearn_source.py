"""Source loader: sklearn built-in datasets (covertype, etc.)."""
from __future__ import annotations

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

# Map sklearn dataset names -> import path of the loader fn.
_SKLEARN_LOADERS = {
    "covertype": ("sklearn.datasets", "fetch_covtype"),
    "kddcup99":  ("sklearn.datasets", "fetch_kddcup99"),
    "20newsgroups_vectorized": ("sklearn.datasets", "fetch_20newsgroups_vectorized"),
}


@source("sklearn")
def load_sklearn(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    if not spec.name:
        raise ValueError("sklearn source: profile.source.name is required")
    name = spec.name
    if name not in _SKLEARN_LOADERS:
        raise KeyError(f"sklearn source: dataset {name!r} not supported "
                       f"(supported: {sorted(_SKLEARN_LOADERS)})")
    module, fn_name = _SKLEARN_LOADERS[name]
    import importlib
    mod = importlib.import_module(module)
    fetch_fn = getattr(mod, fn_name)
    bunch = fetch_fn(as_frame=True)
    df = bunch.data.copy().reset_index(drop=True)
    df[label] = pd.Series(bunch.target).astype(str).reset_index(drop=True).values
    return df, label
