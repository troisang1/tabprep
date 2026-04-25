"""Bootstrap smoke tests — no network access, no real data sources."""
from __future__ import annotations

import io
import textwrap

import numpy as np
import pandas as pd

from tabprep.core.canonical import write_canonical_csv
from tabprep.core.hashing import sha256_of_file
from tabprep.core.profile import load_profile
from tabprep.core.splits import stratified_class_balanced
from tabprep.ops import OP_REGISTRY


def test_canonical_csv_is_byte_stable(tmp_path):
    df = pd.DataFrame({
        "b": [1.0, 2.5, 3.125],
        "a": ["x", "y", "z"],
        "c": [True, False, True],
    })
    out1 = tmp_path / "one.csv"
    out2 = tmp_path / "two.csv"
    write_canonical_csv(df, out1, precision=4, row_shuffle_seed=7)
    write_canonical_csv(df, out2, precision=4, row_shuffle_seed=7)
    assert sha256_of_file(out1) == sha256_of_file(out2)
    # Columns alphabetised:
    header = out1.read_text(encoding="utf-8").splitlines()[0]
    assert header == "a,b,c"


def test_op_registry_has_essentials():
    assert "filter_min_class_count" in OP_REGISTRY
    assert "rename_label" in OP_REGISTRY
    assert "normalize_label_string" in OP_REGISTRY
    assert "drop_columns" in OP_REGISTRY


def test_stratified_split_is_deterministic():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "f": rng.normal(size=100),
        "label": (["a"] * 50) + (["b"] * 50),
    })
    a = stratified_class_balanced(df, label_col="label",
                                   train_frac=0.6, cal_frac=0.2, test_frac=0.2,
                                   seed=42)
    b = stratified_class_balanced(df, label_col="label",
                                   train_frac=0.6, cal_frac=0.2, test_frac=0.2,
                                   seed=42)
    for x, y in zip(a, b):
        pd.testing.assert_frame_equal(x, y)
    assert len(a[0]) + len(a[1]) + len(a[2]) == len(df)


def test_load_pendigits_profile():
    """The shipped pendigits profile should validate."""
    from pathlib import Path
    p = Path(__file__).parent.parent / "profiles" / "builtin" / "pendigits.yaml"
    prof = load_profile(p)
    assert prof.name == "pendigits"
    assert prof.source.kind == "openml"
    assert any(op.op == "filter_min_class_count" for op in prof.pipeline)
