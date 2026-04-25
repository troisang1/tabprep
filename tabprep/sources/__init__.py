"""Source loaders.

A source produces the *raw* dataframe (label column intact, no cleaning
yet) plus the source's `source_column` name. The pipeline executor takes
over from there.

Each loader returns:
    (df: pd.DataFrame, source_column: str)
"""
from tabprep.sources._registry import SOURCE_REGISTRY, source  # noqa: F401

# Importing populates the registry.
from tabprep.sources import openml_source, sklearn_source, url_source, manual  # noqa: F401, E402
from tabprep.sources import concat_csvs_source, nbaiot_dir_source  # noqa: F401, E402

__all__ = ["SOURCE_REGISTRY", "source"]
