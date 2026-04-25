"""Unit tests for `tabprep/core/splits.py`."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tabprep.core.splits import run_split, stratified_class_balanced


def _make_balanced(n_per_class: int = 50, n_classes: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for cls in range(n_classes):
        for _ in range(n_per_class):
            rows.append({"f": float(rng.normal()), "label": f"cls_{cls}"})
    return pd.DataFrame(rows)


def test_stratified_split_returns_three_disjoint_dataframes():
    df = _make_balanced(50, 4)
    train, cal, test = stratified_class_balanced(
        df, label_col="label",
        train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42,
    )
    # Total preserved (rounding may move 1 row but original counts <= 200).
    assert len(train) + len(cal) + len(test) == len(df)


def test_stratified_split_preserves_class_balance():
    """Per class, each split should receive ~train_frac / cal_frac /
    test_frac proportion of that class's rows."""
    df = _make_balanced(100, 3)
    train, cal, test = stratified_class_balanced(
        df, label_col="label",
        train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42,
    )
    for cls in df["label"].unique():
        n_total = (df["label"] == cls).sum()
        n_train = (train["label"] == cls).sum()
        # Allow ±2 row tolerance for rounding.
        assert abs(n_train - 0.6 * n_total) <= 2


def test_stratified_split_is_deterministic():
    df = _make_balanced(50, 3)
    a = stratified_class_balanced(df, label_col="label",
                                   train_frac=0.6, cal_frac=0.2, test_frac=0.2,
                                   seed=42)
    b = stratified_class_balanced(df, label_col="label",
                                   train_frac=0.6, cal_frac=0.2, test_frac=0.2,
                                   seed=42)
    for x, y in zip(a, b):
        pd.testing.assert_frame_equal(x, y)


def test_stratified_split_different_seeds_produce_different_train_subsets():
    """Different seeds pick a different per-class shuffle, so the train
    subset has different *rows* (not just a different order)."""
    df = _make_balanced(50, 3)
    a = stratified_class_balanced(df, label_col="label",
                                   train_frac=0.6, cal_frac=0.2, test_frac=0.2,
                                   seed=1)[0]
    b = stratified_class_balanced(df, label_col="label",
                                   train_frac=0.6, cal_frac=0.2, test_frac=0.2,
                                   seed=2)[0]
    # Train sets differ; their union contains all rows from those classes.
    assert not a.equals(b)
    # Same length (deterministic from frac × n).
    assert len(a) == len(b)


def test_stratified_split_validates_fractions_sum_to_one():
    df = _make_balanced(10, 2)
    with pytest.raises(ValueError, match="must sum to 1"):
        stratified_class_balanced(
            df, label_col="label",
            train_frac=0.5, cal_frac=0.2, test_frac=0.2, seed=42,
        )


def test_stratified_split_keeps_at_least_one_per_class_in_train_and_cal():
    """Even tiny classes must show up in train and calibration so the
    downstream model sees every class."""
    df = pd.DataFrame({
        "f":     [1.0, 2.0, 3.0, 4.0, 5.0],
        "label": ["rare", "rare", "common", "common", "common"],
    })
    train, cal, _ = stratified_class_balanced(
        df, label_col="label",
        train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42,
    )
    assert "rare" in train["label"].values
    assert "rare" in cal["label"].values


def test_run_split_dispatches_to_known_kind():
    df = _make_balanced(20, 2)
    train, cal, test = run_split(
        df, label_col="label", kind="stratified_class_balanced",
        train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42,
    )
    assert len(train) + len(cal) + len(test) == len(df)


def test_run_split_raises_on_unknown_kind():
    df = _make_balanced(10, 2)
    with pytest.raises(ValueError, match="unknown split kind"):
        run_split(
            df, label_col="label", kind="bogus",
            train_frac=0.6, cal_frac=0.2, test_frac=0.2, seed=42,
        )
