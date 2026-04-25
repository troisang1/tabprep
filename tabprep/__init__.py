"""tabprep — reproducible tabular dataset preparation.

Quickstart:

    import tabprep

    # Prepare a built-in profile and get the result paths + hashes.
    result = tabprep.prepare("pendigits")
    train_df = result.load("train")

    # Or grab all three splits as DataFrames in one call.
    train_df, cal_df, test_df = tabprep.load_splits("pendigits")

    # Use a custom profile YAML.
    result = tabprep.prepare("./my_profile.yaml", output_dir="./out")

    # List what's available.
    for prof in tabprep.list_profiles():
        print(prof.name, prof.version, prof.description.splitlines()[0])
"""

__version__ = "0.1.0"

from tabprep.api import (
    PrepareResult,
    list_profiles,
    load_split,
    load_splits,
    prepare,
    resolve_profile,
)
from tabprep.core.hashing import canonical_sha256_of_file
from tabprep.core.pipeline import run_pipeline
from tabprep.core.profile import Profile, load_profile

__all__ = [
    "__version__",
    # High-level API
    "prepare",
    "load_splits",
    "load_split",
    "list_profiles",
    "resolve_profile",
    "PrepareResult",
    # Low-level building blocks
    "Profile",
    "load_profile",
    "run_pipeline",
    "canonical_sha256_of_file",
]
