"""tabprep quickstart — the four most common usage patterns.

Run from the project root:

    python examples/quickstart.py
"""
from __future__ import annotations

import tabprep


def example_1_one_line_dataframes():
    """Get train/cal/test DataFrames in a single call."""
    train_df, cal_df, test_df = tabprep.load_splits("pendigits")
    print(f"[1] pendigits   train={train_df.shape}  cal={cal_df.shape}  test={test_df.shape}")
    print(f"    label classes: {sorted(train_df['label'].unique())}")


def example_2_inspect_paths_and_hashes():
    """Use prepare() when you want explicit access to the output paths,
    sha256 fingerprints, and the verification status against the
    profile's pinned `expected_hashes`.
    """
    result = tabprep.prepare("letter", quiet=True)
    print(f"[2] letter      output_dir={result.output_dir}")
    print(f"    verified: {result.verified}")
    for fname, sha in result.sha256.items():
        print(f"      {fname:<18} sha256={sha[:16]}…")


def example_3_custom_output_dir():
    """Custom output dir and skip the cleaning pipeline (raw loader output
    only — useful for inspection; pinned hashes will not match)."""
    result = tabprep.prepare(
        "optdigits",
        output_dir="./out_quickstart",
        skip_pipeline=False,                         # full pipeline (the default)
        quiet=True,
    )
    print(f"[3] optdigits   wrote to {result.output_dir}, verified={result.verified}")


def example_4_user_yaml(tmp_path=None):
    """Pass a path to a custom YAML — same API surface as a built-in.

    In practice your YAML lives wherever you author it; here we copy a
    shipped profile to a tempfile so the example runs from any cwd.
    """
    import shutil
    import tempfile
    from pathlib import Path

    src = Path(tabprep.__file__).parent / "profiles" / "pendigits.yaml"
    tmp = tempfile.NamedTemporaryFile(
        suffix=".yaml", delete=False, mode="w", encoding="utf-8"
    )
    tmp.close()
    shutil.copy(src, tmp.name)

    result = tabprep.prepare(tmp.name, quiet=True)
    print(f"[4] custom YAML {Path(tmp.name).name} → {result.output_dir.name}, "
          f"verified={result.verified}")


def example_5_list_profiles():
    """Discover what's built in."""
    profiles = tabprep.list_profiles()
    print(f"[5] {len(profiles)} built-in profiles:")
    for p in profiles[:5]:
        first_line = (p.description or "").splitlines()[0].strip()
        print(f"      {p.name:<14} v{p.version}   {first_line[:60]}")
    print(f"      … ({len(profiles) - 5} more)")


if __name__ == "__main__":
    example_1_one_line_dataframes()
    example_2_inspect_paths_and_hashes()
    example_3_custom_output_dir()
    example_4_user_yaml()
    example_5_list_profiles()
