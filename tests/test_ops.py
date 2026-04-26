"""Unit tests for every pipeline op in `tabprep/ops/`.

Each op gets a happy-path test plus enough edge cases to lock the
contract (sentinel values, missing columns, deterministic seeded
sampling, etc.). The OP_REGISTRY itself is also asserted so a typo in
a `@op("name")` decorator surfaces as a test failure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tabprep.ops import OP_REGISTRY


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EXPECTED_OPS = {
    # label
    "rename_label", "normalize_label_string",
    # clean
    "drop_columns", "drop_constant_columns", "drop_ip_columns",
    "drop_high_nan_columns", "replace_inf", "fill_nan", "coerce_numeric",
    "drop_constant_prefix_columns", "strip_column_whitespace",
    "rename_columns", "filter_rows_label_isnull",
    # filter
    "filter_min_class_count", "drop_classes", "keep_classes",
    # sample
    "cap_per_class", "balanced_subsample", "stratified_fraction_sample",
    # encode
    "encode_categoricals", "rename_features_f0fN",
}


def test_registry_contains_all_expected_ops():
    """A typo in any @op("...") decorator surfaces here. Extras are
    fine (a new op was added since this test was written); missing
    ones are not."""
    missing = EXPECTED_OPS - set(OP_REGISTRY)
    assert not missing, f"expected ops missing from registry: {missing}"


# ---------------------------------------------------------------------------
# label.py — rename_label
# ---------------------------------------------------------------------------

def test_rename_label_renames_source_to_target():
    df = pd.DataFrame({"x": [1, 2], "type": ["a", "b"]})
    out = OP_REGISTRY["rename_label"](
        df, label_col="label", source_column="type", rename_to="label",
    )
    assert "label" in out.columns
    assert "type" not in out.columns
    assert out["label"].tolist() == ["a", "b"]


def test_rename_label_drops_existing_label_column():
    """ToN-IoT case: a binary `label` column exists alongside the multi-class
    target. The pre-existing `label` column must be dropped first to avoid
    a duplicate-column DataFrame after rename."""
    df = pd.DataFrame({"x": [1, 2], "label": [0, 1], "type": ["a", "b"]})
    out = OP_REGISTRY["rename_label"](
        df, label_col="label", source_column="type", rename_to="label",
    )
    assert list(out.columns).count("label") == 1
    assert out["label"].tolist() == ["a", "b"]


def test_rename_label_noop_when_source_eq_target():
    df = pd.DataFrame({"x": [1, 2], "label": ["a", "b"]})
    out = OP_REGISTRY["rename_label"](
        df, label_col="label", source_column="label", rename_to="label",
    )
    pd.testing.assert_frame_equal(out, df)


def test_rename_label_raises_on_missing_source_column():
    df = pd.DataFrame({"x": [1, 2]})
    with pytest.raises(KeyError, match="source_column"):
        OP_REGISTRY["rename_label"](
            df, label_col="label", source_column="missing", rename_to="label",
        )


# ---------------------------------------------------------------------------
# label.py — normalize_label_string
# ---------------------------------------------------------------------------

def test_normalize_label_string_lowercase_underscore():
    df = pd.DataFrame({"label": ["DDoS Attack", "Mirai-Botnet", "  benign "]})
    out = OP_REGISTRY["normalize_label_string"](
        df, label_col="label", method="lowercase_underscore",
    )
    assert out["label"].tolist() == ["ddos_attack", "mirai_botnet", "benign"]


def test_normalize_label_string_none_method():
    df = pd.DataFrame({"label": ["X", "Y"]})
    out = OP_REGISTRY["normalize_label_string"](
        df, label_col="label", method="none",
    )
    assert out["label"].tolist() == ["X", "Y"]


def test_normalize_label_string_raises_on_unknown_method():
    df = pd.DataFrame({"label": ["a"]})
    with pytest.raises(ValueError, match="unknown normalize method"):
        OP_REGISTRY["normalize_label_string"](
            df, label_col="label", method="snake_oil",
        )


def test_normalize_label_string_raises_on_missing_label_col():
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(KeyError, match="label_col"):
        OP_REGISTRY["normalize_label_string"](
            df, label_col="missing", method="lowercase_underscore",
        )


# ---------------------------------------------------------------------------
# clean.py — drop_columns
# ---------------------------------------------------------------------------

def test_drop_columns_drops_named_columns():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    out = OP_REGISTRY["drop_columns"](df, label_col="label", columns=["a", "c"])
    assert list(out.columns) == ["b"]


def test_drop_columns_ignores_missing_columns():
    df = pd.DataFrame({"a": [1], "b": [2]})
    out = OP_REGISTRY["drop_columns"](
        df, label_col="label", columns=["a", "missing"],
    )
    assert list(out.columns) == ["b"]


def test_drop_columns_empty_list_is_noop():
    df = pd.DataFrame({"a": [1]})
    out = OP_REGISTRY["drop_columns"](df, label_col="label", columns=[])
    pd.testing.assert_frame_equal(out, df)


# ---------------------------------------------------------------------------
# clean.py — drop_constant_columns
# ---------------------------------------------------------------------------

def test_drop_constant_columns_drops_single_value_columns():
    df = pd.DataFrame({"x": [1, 1, 1], "y": [1, 2, 3], "label": ["a", "a", "a"]})
    out = OP_REGISTRY["drop_constant_columns"](df, label_col="label")
    assert "x" not in out.columns
    assert "y" in out.columns
    # The label column is constant but never dropped.
    assert "label" in out.columns


def test_drop_constant_columns_treats_all_nan_as_constant():
    df = pd.DataFrame({"x": [np.nan, np.nan], "y": [1, 2], "label": ["a", "b"]})
    out = OP_REGISTRY["drop_constant_columns"](df, label_col="label")
    assert "x" not in out.columns


# ---------------------------------------------------------------------------
# clean.py — drop_ip_columns
# ---------------------------------------------------------------------------

def test_drop_ip_columns_drops_common_patterns():
    df = pd.DataFrame({
        "src_ip": ["1.2.3.4"], "dst_ip": ["5.6.7.8"],
        "ip.src_host": ["a"], "ip.dst_host": ["b"],
        "srcip": ["x"], "dstip": ["y"],
        "feature": [1.0],
        "label": ["normal"],
    })
    out = OP_REGISTRY["drop_ip_columns"](df, label_col="label")
    assert set(out.columns) == {"feature", "label"}


def test_drop_ip_columns_case_insensitive():
    df = pd.DataFrame({"SRC_IP": ["1.2.3.4"], "feat": [1.0], "label": ["a"]})
    out = OP_REGISTRY["drop_ip_columns"](df, label_col="label")
    assert "SRC_IP" not in out.columns


def test_drop_ip_columns_does_not_drop_label():
    """Even if the label literally were named 'src_ip' (unlikely), it
    must not be dropped — the implementation explicitly skips label_col.
    """
    df = pd.DataFrame({"src_ip": ["a"], "feat": [1.0]})
    out = OP_REGISTRY["drop_ip_columns"](df, label_col="src_ip")
    assert "src_ip" in out.columns


# ---------------------------------------------------------------------------
# clean.py — drop_high_nan_columns
# ---------------------------------------------------------------------------

def test_drop_high_nan_columns_drops_above_threshold():
    df = pd.DataFrame({
        "ok":   [1, 2, 3, 4, 5],                           # 0% nan
        "okay": [1, np.nan, 3, np.nan, 5],                 # 40% nan
        "bad":  [np.nan, np.nan, np.nan, np.nan, 5],       # 80% nan
        "worse":[np.nan, np.nan, np.nan, np.nan, np.nan],  # 100% nan
        "label":["a", "b", "a", "b", "a"],
    })
    # threshold=0.7 → drop columns with >70% nan ("worse" only — "bad" is exactly 80%).
    # Implementation uses strictly > threshold, so 0.7 drops both 80% (>0.7) and 100% (>0.7).
    out = OP_REGISTRY["drop_high_nan_columns"](df, label_col="label", threshold=0.7)
    assert "ok" in out.columns
    assert "okay" in out.columns
    assert "bad" not in out.columns
    assert "worse" not in out.columns


def test_drop_high_nan_columns_label_never_dropped():
    df = pd.DataFrame({
        "feat":  [1, 2, 3],
        "label": [np.nan, np.nan, np.nan],
    })
    out = OP_REGISTRY["drop_high_nan_columns"](df, label_col="label", threshold=0.5)
    assert "label" in out.columns


# ---------------------------------------------------------------------------
# clean.py — replace_inf
# ---------------------------------------------------------------------------

def test_replace_inf_default_replaces_with_nan():
    df = pd.DataFrame({"x": [1.0, np.inf, -np.inf, 2.0]})
    out = OP_REGISTRY["replace_inf"](df, label_col="label")
    assert pd.isna(out["x"].iloc[1])
    assert pd.isna(out["x"].iloc[2])
    assert out["x"].iloc[0] == 1.0


def test_replace_inf_with_explicit_value():
    df = pd.DataFrame({"x": [1.0, np.inf, -np.inf]})
    out = OP_REGISTRY["replace_inf"](df, label_col="label", value=0.0)
    assert out["x"].tolist() == [1.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# clean.py — fill_nan
# ---------------------------------------------------------------------------

def test_fill_nan_default_fills_with_zero():
    df = pd.DataFrame({"x": [1.0, np.nan, 2.0]})
    out = OP_REGISTRY["fill_nan"](df, label_col="label")
    assert out["x"].tolist() == [1.0, 0.0, 2.0]


def test_fill_nan_with_custom_value():
    df = pd.DataFrame({"x": [1.0, np.nan]})
    out = OP_REGISTRY["fill_nan"](df, label_col="label", value=-1.0)
    assert out["x"].tolist() == [1.0, -1.0]


# ---------------------------------------------------------------------------
# clean.py — coerce_numeric
# ---------------------------------------------------------------------------

def test_coerce_numeric_converts_string_columns():
    df = pd.DataFrame({"x": ["1.5", "2.5", "bad"], "label": ["a", "b", "c"]})
    out = OP_REGISTRY["coerce_numeric"](df, label_col="label")
    # "bad" → NaN
    assert out["x"].iloc[0] == 1.5
    assert out["x"].iloc[1] == 2.5
    assert pd.isna(out["x"].iloc[2])


def test_coerce_numeric_skips_label_column():
    df = pd.DataFrame({"x": ["1"], "label": ["string-label"]})
    out = OP_REGISTRY["coerce_numeric"](df, label_col="label")
    assert out["label"].iloc[0] == "string-label"


def test_coerce_numeric_skips_already_numeric_columns():
    df = pd.DataFrame({"x": [1, 2], "label": ["a", "b"]})
    out = OP_REGISTRY["coerce_numeric"](df, label_col="label")
    assert out["x"].dtype == np.int64 or pd.api.types.is_integer_dtype(out["x"])


# ---------------------------------------------------------------------------
# clean.py — drop_constant_prefix_columns
# ---------------------------------------------------------------------------

def test_drop_constant_prefix_columns():
    df = pd.DataFrame({
        "ssl_ver": ["-", "-", "-"],          # constant + ssl_ prefix → drop
        "ssl_cipher": ["a", "b", "a"],       # variable + ssl_ prefix → keep
        "dns_ttl": ["-", "-", "-"],          # constant + dns_ prefix → drop
        "feat": [1, 2, 3],                   # no matching prefix → keep
        "label": ["a", "b", "a"],
    })
    out = OP_REGISTRY["drop_constant_prefix_columns"](
        df, label_col="label", prefixes=["ssl_", "dns_"],
    )
    assert "ssl_ver" not in out.columns
    assert "ssl_cipher" in out.columns
    assert "dns_ttl" not in out.columns
    assert "feat" in out.columns


def test_drop_constant_prefix_columns_empty_list_is_noop():
    df = pd.DataFrame({"x": [1, 1], "label": ["a", "a"]})
    out = OP_REGISTRY["drop_constant_prefix_columns"](
        df, label_col="label", prefixes=[],
    )
    pd.testing.assert_frame_equal(out, df)


# ---------------------------------------------------------------------------
# clean.py — strip_column_whitespace
# ---------------------------------------------------------------------------

def test_strip_column_whitespace_strips_leading_trailing():
    df = pd.DataFrame({" Label ": ["a"], "  Flow ID": [1]})
    out = OP_REGISTRY["strip_column_whitespace"](df, label_col="Label")
    assert "Label" in out.columns
    assert "Flow ID" in out.columns
    assert " Label " not in out.columns


# ---------------------------------------------------------------------------
# clean.py — rename_columns
# ---------------------------------------------------------------------------

def test_rename_columns_applies_explicit_mapping():
    df = pd.DataFrame({"old_a": [1], "old_b": [2]})
    out = OP_REGISTRY["rename_columns"](
        df, label_col="label",
        mapping={"old_a": "new_a", "old_b": "new_b"},
    )
    assert list(out.columns) == ["new_a", "new_b"]


def test_rename_columns_empty_mapping_is_noop():
    df = pd.DataFrame({"a": [1]})
    out = OP_REGISTRY["rename_columns"](df, label_col="label", mapping={})
    pd.testing.assert_frame_equal(out, df)


# ---------------------------------------------------------------------------
# clean.py — filter_rows_label_isnull
# ---------------------------------------------------------------------------

def test_filter_rows_label_isnull_drops_nan_empty_and_literal_nan():
    df = pd.DataFrame({
        "x":     [1, 2, 3, 4, 5],
        "label": ["a", np.nan, "", "nan", "b"],
    })
    out = OP_REGISTRY["filter_rows_label_isnull"](df, label_col="label")
    assert out["label"].tolist() == ["a", "b"]


def test_filter_rows_label_isnull_returns_unchanged_when_label_missing():
    df = pd.DataFrame({"x": [1]})
    out = OP_REGISTRY["filter_rows_label_isnull"](df, label_col="label")
    pd.testing.assert_frame_equal(out, df)


# ---------------------------------------------------------------------------
# filter.py — filter_min_class_count
# ---------------------------------------------------------------------------

def test_filter_min_class_count_drops_rare_classes():
    df = pd.DataFrame({
        "x":     list(range(10)),
        "label": ["a"] * 5 + ["b"] * 3 + ["c"] * 2,
    })
    out = OP_REGISTRY["filter_min_class_count"](df, label_col="label", min_count=4)
    assert set(out["label"].unique()) == {"a"}


def test_filter_min_class_count_raises_on_missing_label():
    df = pd.DataFrame({"x": [1]})
    with pytest.raises(KeyError, match="label_col"):
        OP_REGISTRY["filter_min_class_count"](
            df, label_col="missing", min_count=1,
        )


# ---------------------------------------------------------------------------
# filter.py — drop_classes / keep_classes
# ---------------------------------------------------------------------------

def test_drop_classes_drops_listed_labels():
    df = pd.DataFrame({"x": [1, 2, 3], "label": ["a", "b", "c"]})
    out = OP_REGISTRY["drop_classes"](
        df, label_col="label", labels=["b"],
    )
    assert out["label"].tolist() == ["a", "c"]


def test_drop_classes_empty_list_is_noop():
    df = pd.DataFrame({"label": ["a", "b"]})
    out = OP_REGISTRY["drop_classes"](df, label_col="label", labels=[])
    pd.testing.assert_frame_equal(out, df)


def test_keep_classes_keeps_listed_labels():
    df = pd.DataFrame({"x": [1, 2, 3], "label": ["a", "b", "c"]})
    out = OP_REGISTRY["keep_classes"](
        df, label_col="label", labels=["a", "c"],
    )
    assert out["label"].tolist() == ["a", "c"]


def test_keep_classes_empty_list_is_noop():
    df = pd.DataFrame({"label": ["a", "b"]})
    out = OP_REGISTRY["keep_classes"](df, label_col="label", labels=[])
    pd.testing.assert_frame_equal(out, df)


def test_drop_classes_handles_int_labels_as_strings():
    """Implementation casts both sides to str, so int labels in the YAML
    list still match int-typed dataframe labels."""
    df = pd.DataFrame({"label": [0, 1, 2]})
    out = OP_REGISTRY["drop_classes"](df, label_col="label", labels=["1"])
    assert out["label"].tolist() == [0, 2]


# ---------------------------------------------------------------------------
# sample.py — cap_per_class
# ---------------------------------------------------------------------------

def test_cap_per_class_caps_each_class():
    df = pd.DataFrame({
        "x":     list(range(15)),
        "label": ["a"] * 10 + ["b"] * 5,
    })
    out = OP_REGISTRY["cap_per_class"](
        df, label_col="label", cap=3, seed=42,
    )
    assert (out["label"] == "a").sum() == 3
    assert (out["label"] == "b").sum() == 3


def test_cap_per_class_keeps_small_classes_whole():
    df = pd.DataFrame({"x": [1, 2], "label": ["rare", "rare"]})
    out = OP_REGISTRY["cap_per_class"](
        df, label_col="label", cap=10, seed=42,
    )
    assert len(out) == 2


def test_cap_per_class_is_deterministic():
    df = pd.DataFrame({
        "x":     list(range(20)),
        "label": ["a"] * 20,
    })
    a = OP_REGISTRY["cap_per_class"](df, label_col="label", cap=5, seed=42)
    b = OP_REGISTRY["cap_per_class"](df, label_col="label", cap=5, seed=42)
    pd.testing.assert_frame_equal(a, b)


# ---------------------------------------------------------------------------
# sample.py — balanced_subsample
# ---------------------------------------------------------------------------

def test_balanced_subsample_caps_to_max_total_balanced():
    df = pd.DataFrame({
        "x":     list(range(30)),
        "label": ["a"] * 10 + ["b"] * 10 + ["c"] * 10,
    })
    out = OP_REGISTRY["balanced_subsample"](
        df, label_col="label", max_total=15, seed=42,
    )
    # 15 / 3 classes = 5 per class.
    counts = out["label"].value_counts().to_dict()
    assert counts == {"a": 5, "b": 5, "c": 5}


def test_balanced_subsample_one_class():
    df = pd.DataFrame({"x": list(range(10)), "label": ["only"] * 10})
    out = OP_REGISTRY["balanced_subsample"](
        df, label_col="label", max_total=4, seed=42,
    )
    assert len(out) == 4


def test_balanced_subsample_zero_classes_returns_input():
    df = pd.DataFrame({"x": [], "label": []}).astype({"x": "int64", "label": "object"})
    out = OP_REGISTRY["balanced_subsample"](
        df, label_col="label", max_total=10, seed=42,
    )
    assert len(out) == 0


# ---------------------------------------------------------------------------
# sample.py — stratified_fraction_sample
# ---------------------------------------------------------------------------

def test_stratified_fraction_preserves_per_class_proportion():
    """5% of a 700/200/100 distribution → 35/10/5 — proportions unchanged."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "x": rng.normal(size=1000),
        "label": (["a"] * 700) + (["b"] * 200) + (["c"] * 100),
    })
    out = OP_REGISTRY["stratified_fraction_sample"](
        df, label_col="label", fraction=0.05, seed=42,
    )
    counts = out["label"].value_counts()
    assert counts["a"] == 35
    assert counts["b"] == 10
    assert counts["c"] == 5


def test_stratified_fraction_floor_keeps_tiny_class():
    """A single-row class survives floor() with the floor=1 rule."""
    df = pd.DataFrame({
        "x": list(range(101)),
        "label": (["a"] * 100) + ["rare"],
    })
    out = OP_REGISTRY["stratified_fraction_sample"](
        df, label_col="label", fraction=0.05, seed=42,
    )
    counts = out["label"].value_counts()
    assert counts["a"] == 5
    assert counts["rare"] == 1


def test_stratified_fraction_deterministic():
    df = pd.DataFrame({
        "x": list(range(100)),
        "label": (["a"] * 50) + (["b"] * 50),
    })
    a = OP_REGISTRY["stratified_fraction_sample"](
        df, label_col="label", fraction=0.5, seed=42,
    )
    b = OP_REGISTRY["stratified_fraction_sample"](
        df, label_col="label", fraction=0.5, seed=42,
    )
    pd.testing.assert_frame_equal(a, b)


def test_stratified_fraction_one_returns_full_distribution():
    df = pd.DataFrame({
        "x": list(range(50)),
        "label": (["a"] * 30) + (["b"] * 20),
    })
    out = OP_REGISTRY["stratified_fraction_sample"](
        df, label_col="label", fraction=1.0, seed=42,
    )
    assert len(out) == 50
    counts = out["label"].value_counts()
    assert counts["a"] == 30
    assert counts["b"] == 20


def test_stratified_fraction_rejects_invalid_fraction():
    df = pd.DataFrame({"x": [1, 2], "label": ["a", "b"]})
    with pytest.raises(ValueError):
        OP_REGISTRY["stratified_fraction_sample"](
            df, label_col="label", fraction=0.0, seed=42,
        )
    with pytest.raises(ValueError):
        OP_REGISTRY["stratified_fraction_sample"](
            df, label_col="label", fraction=1.5, seed=42,
        )


def test_stratified_fraction_missing_label_raises():
    df = pd.DataFrame({"x": [1, 2]})
    with pytest.raises(KeyError):
        OP_REGISTRY["stratified_fraction_sample"](
            df, label_col="label", fraction=0.5, seed=42,
        )


# ---------------------------------------------------------------------------
# encode.py — encode_categoricals
# ---------------------------------------------------------------------------

def test_encode_categoricals_one_hots_low_cardinality_strings():
    df = pd.DataFrame({
        "proto": ["tcp", "udp", "tcp", "icmp"],
        "label": ["a", "b", "c", "d"],
    })
    out = OP_REGISTRY["encode_categoricals"](
        df, label_col="label", max_cardinality=10, method="onehot",
    )
    # Original column gone; one-hot columns added with proto_ prefix.
    assert "proto" not in out.columns
    assert any(c.startswith("proto_") for c in out.columns)


def test_encode_categoricals_one_hot_columns_are_sorted():
    """`pd.get_dummies` sorts categories — the lowercase+strip step plus
    sorted columns input gives a deterministic output column order."""
    df = pd.DataFrame({
        "proto": ["tcp", "UDP", " tcp ", "udp"],
        "label": ["a", "b", "a", "b"],
    })
    out = OP_REGISTRY["encode_categoricals"](
        df, label_col="label", max_cardinality=10, method="onehot",
    )
    proto_cols = sorted(c for c in out.columns if c.startswith("proto_"))
    # Lower + strip → "tcp" and "udp"
    assert proto_cols == ["proto_tcp", "proto_udp"]


def test_encode_categoricals_promotes_mostly_numeric_strings_to_numeric():
    """If a column is >90% numeric strings (with `-` as sentinel NaN),
    convert it in place rather than one-hot it. Threshold is strict
    `> 0.9`, so use 11/12 ≈ 91.7% to clear it."""
    values = [f"{i}.5" for i in range(11)] + ["-"]
    df = pd.DataFrame({
        "almost_num": values,
        "label": ["a"] * 12,
    })
    out = OP_REGISTRY["encode_categoricals"](
        df, label_col="label", max_cardinality=10,
    )
    assert "almost_num" in out.columns
    assert pd.api.types.is_numeric_dtype(out["almost_num"])
    assert out["almost_num"].iloc[0] == 0.5
    assert pd.isna(out["almost_num"].iloc[11])


def test_encode_categoricals_drops_high_cardinality_strings():
    df = pd.DataFrame({
        "uid": [f"u{i}" for i in range(10)],     # 10 unique
        "label": ["a"] * 10,
    })
    out = OP_REGISTRY["encode_categoricals"](
        df, label_col="label", max_cardinality=3,
    )
    assert "uid" not in out.columns
    # No one-hot columns created.
    assert all(not c.startswith("uid_") for c in out.columns)


def test_encode_categoricals_drops_constant_strings():
    df = pd.DataFrame({"const": ["x", "x", "x"], "label": ["a", "b", "c"]})
    out = OP_REGISTRY["encode_categoricals"](df, label_col="label")
    assert "const" not in out.columns


def test_encode_categoricals_raises_on_unsupported_method():
    df = pd.DataFrame({"x": ["a"], "label": ["b"]})
    with pytest.raises(ValueError, match="unsupported encode method"):
        OP_REGISTRY["encode_categoricals"](
            df, label_col="label", method="target",
        )


def test_encode_categoricals_skips_label_column():
    """The label is a string column with potentially many values, but the
    encoder must never touch it."""
    df = pd.DataFrame({
        "feat":  ["a", "b", "a", "b"],
        "label": ["x1", "x2", "x3", "x4"],          # 4 unique strings
    })
    out = OP_REGISTRY["encode_categoricals"](
        df, label_col="label", max_cardinality=10,
    )
    assert "label" in out.columns
    assert out["label"].tolist() == ["x1", "x2", "x3", "x4"]


# ---------------------------------------------------------------------------
# encode.py — rename_features_f0fN
# ---------------------------------------------------------------------------

def test_rename_features_f0fN_renames_in_source_order():
    df = pd.DataFrame({"V1": [1], "V2": [2], "V3": [3], "label": ["a"]})
    out = OP_REGISTRY["rename_features_f0fN"](df, label_col="label")
    assert list(out.columns) == ["f0", "f1", "f2", "label"]


def test_rename_features_f0fN_preserves_label_position():
    df = pd.DataFrame({"a": [1], "label": ["x"], "b": [2]})
    out = OP_REGISTRY["rename_features_f0fN"](df, label_col="label")
    # `label` keeps its position; non-label columns become f0, f1 in order.
    assert list(out.columns) == ["f0", "label", "f1"]


def test_rename_features_f0fN_no_features_is_noop():
    df = pd.DataFrame({"label": ["a", "b"]})
    out = OP_REGISTRY["rename_features_f0fN"](df, label_col="label")
    assert list(out.columns) == ["label"]
