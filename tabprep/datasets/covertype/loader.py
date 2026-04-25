"""Covertype loader: fetches Forest Cover Type via sklearn.fetch_covtype.

Output shape matches the legacy `tabprep/sources/sklearn_source.py`'s
`covertype` branch byte-for-byte so migrating the profile produces
identical canonical CSVs (the pinned `expected_hashes` keep matching):

    bunch = fetch_covtype(as_frame=True)   # or fetch_covtype() on older sklearn
    data  = getattr(bunch, "data", bunch)
    target = getattr(bunch, "target", None)
    if not isinstance(data, pd.DataFrame):
        feature_names = getattr(bunch, "feature_names", None) or [f"f{i}" for ...]
        data = pd.DataFrame(data, columns=list(feature_names))
    df = data.reset_index(drop=True).copy()
    df[label_col] = pd.Series(target).astype(str).reset_index(drop=True).values
    return df, label_col
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


@loader("covertype")
class CovertypeLoader(BaseLoader):
    """Reader for the covertype dataset via `sklearn.datasets.fetch_covtype`.

    Profile usage:
        loader: covertype
        loader_options: {}              # no options needed
    """

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        from sklearn.datasets import fetch_covtype

        # Older sklearn versions silently fall back to ndarray output even
        # when `as_frame=True` is requested if `pandas` isn't on the path
        # the loader checks; newer versions reliably return a Bunch with a
        # DataFrame `data` and a Series `target`. Normalise both.
        try:
            bunch = fetch_covtype(as_frame=True)
        except TypeError:
            bunch = fetch_covtype()

        data = getattr(bunch, "data", bunch)
        target = getattr(bunch, "target", None)
        if target is None:
            raise RuntimeError(
                "covertype loader: bunch has no 'target' attribute"
            )

        if not isinstance(data, pd.DataFrame):
            feature_names = getattr(bunch, "feature_names", None)
            if feature_names is None or len(feature_names) != data.shape[1]:
                feature_names = [f"f{i}" for i in range(data.shape[1])]
            data = pd.DataFrame(data, columns=list(feature_names))

        df = data.reset_index(drop=True).copy()
        df[label_col] = pd.Series(target).astype(str).reset_index(drop=True).values
        return df, label_col
