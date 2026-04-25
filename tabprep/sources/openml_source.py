"""Source loader: OpenML datasets via sklearn.datasets.fetch_openml."""
from __future__ import annotations

import pandas as pd

from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source


@source("openml")
def load_openml(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    """Fetch via sklearn's OpenML proxy. `name` is the OpenML dataset id
    (string identifier such as "pendigits"); the version pinned to 1 by
    default for reproducibility — override by appending `@<version>` to
    the name (e.g. `pendigits@1`).
    """
    if not spec.name:
        raise ValueError("openml source: profile.source.name is required")

    from sklearn.datasets import fetch_openml

    name = spec.name
    version: int | str = 1
    if "@" in name:
        name, ver = name.split("@", 1)
        version = int(ver) if ver.isdigit() else ver

    bunch = fetch_openml(name, version=version, as_frame=True, parser="auto")
    X = bunch.data.copy()
    # OpenML targets are sometimes Categorical; coerce to string for label.
    y = bunch.target.astype(str).reset_index(drop=True)
    df = X.reset_index(drop=True).copy()
    df[label] = y.values
    return df, label
