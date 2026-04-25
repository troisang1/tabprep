"""OpenML loader: fetches an OpenML dataset via sklearn and returns
`(df, label_col)`.

The seven profiles in this family (pendigits, letter, optdigits,
satimage, segment, texture, har) all use OpenML version 1 by default,
which is the canonical UCI mirror. Override per-profile via
`loader_options.openml_version`.

Output shape matches the legacy `tabprep/sources/openml_source.py`
exactly so migrating profiles produces byte-identical CSVs (the pinned
`expected_hashes` in each profile must keep matching after the move):

    bunch = fetch_openml(name, version, as_frame=True, parser="auto")
    df = bunch.data.reset_index(drop=True).copy()
    df[label_col] = bunch.target.astype(str).reset_index(drop=True).values
    return df, label_col
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


@loader("openml")
class OpenMLLoader(BaseLoader):
    """Reader for OpenML datasets via `sklearn.datasets.fetch_openml`.

    Profile usage:
        loader: openml
        loader_options:
          openml_name: pendigits      # OpenML dataset key
          openml_version: 1           # optional, defaults to 1
    """

    DEFAULT_VERSION: int = 1

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        openml_name: str | None = None,
        openml_version: int | str = DEFAULT_VERSION,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        # Fall back to the cached_at tail directory if the profile
        # didn't pass `openml_name` explicitly. Both forms are fine;
        # the explicit form is the documented one.
        name = openml_name or Path(raw_dir).name
        if not name:
            raise ValueError(
                "openml loader: cannot determine OpenML dataset name. "
                "Set `loader_options.openml_name` in the profile."
            )

        from sklearn.datasets import fetch_openml

        bunch = fetch_openml(
            name,
            version=openml_version,
            as_frame=True,
            parser="auto",
        )
        # OpenML targets are sometimes Categorical; coerce to string for label.
        y = bunch.target.astype(str).reset_index(drop=True)
        df = bunch.data.reset_index(drop=True).copy()
        df[label_col] = y.values
        return df, label_col
