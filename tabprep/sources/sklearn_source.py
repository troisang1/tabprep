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

    # Older sklearn versions silently fall back to ndarray output even when
    # `as_frame=True` is requested if `pandas` isn't on the path the loader
    # checks; newer versions reliably return a Bunch with a DataFrame `data`
    # and a Series `target`. Normalise both.
    try:
        bunch = fetch_fn(as_frame=True)
    except TypeError:
        bunch = fetch_fn()

    data = getattr(bunch, "data", bunch)
    target = getattr(bunch, "target", None)
    if target is None:
        raise RuntimeError(f"sklearn source: {name!r} bunch has no 'target' attribute")

    if not isinstance(data, pd.DataFrame):
        feature_names = getattr(bunch, "feature_names", None)
        if feature_names is None or len(feature_names) != data.shape[1]:
            feature_names = [f"f{i}" for i in range(data.shape[1])]
        data = pd.DataFrame(data, columns=list(feature_names))

    df = data.reset_index(drop=True).copy()
    df[label] = pd.Series(target).astype(str).reset_index(drop=True).values
    return df, label
