"""Unit tests for the Profile schema (`tabprep/core/profile.py`).

Cover both the dataclass-level `__post_init__` validation and the YAML
loader (`load_profile`). The shipped profile YAMLs are exercised
elsewhere; here we focus on edge cases that an authoring user would
hit when writing a new profile.
"""
from __future__ import annotations

import pytest

from tabprep.core.profile import (
    LabelSpec,
    OutputSpec,
    Profile,
    SourceSpec,
    SplitSpec,
    load_profile,
)


# ---------------------------------------------------------------------------
# Profile.__post_init__ validation
# ---------------------------------------------------------------------------

def _legacy_profile(**overrides) -> Profile:
    """Helper: minimal-valid v0.4 (legacy) profile with overrides."""
    base = dict(
        name="t",
        version="0.0",
        description="t",
        label=LabelSpec(source_column="label"),
        pipeline=[],
        split=SplitSpec(),
        output=OutputSpec(),
        source=SourceSpec(kind="manual"),
    )
    base.update(overrides)
    return Profile(**base)


def _v05_profile(**overrides) -> Profile:
    """Helper: minimal-valid v0.5 profile with overrides."""
    base = dict(
        name="t",
        version="0.0",
        description="t",
        label=LabelSpec(source_column="label"),
        pipeline=[],
        split=SplitSpec(),
        output=OutputSpec(),
        downloader="iot23",
        loader="iot23",
        cached_at="raw/t/",
    )
    base.update(overrides)
    return Profile(**base)


def test_legacy_profile_valid():
    prof = _legacy_profile()
    assert prof.source.kind == "manual"
    assert prof.loader is None


def test_v05_profile_valid():
    prof = _v05_profile()
    assert prof.loader == "iot23"
    assert prof.downloader == "iot23"
    assert prof.source is None


def test_split_fractions_must_sum_to_one():
    with pytest.raises(ValueError, match="split fractions must sum"):
        _legacy_profile(split=SplitSpec(train_frac=0.5, cal_frac=0.2, test_frac=0.2))


def test_split_fractions_tolerate_rounding():
    """Allow 0.001 wiggle room for rounding."""
    prof = _legacy_profile(
        split=SplitSpec(train_frac=0.6, cal_frac=0.2, test_frac=0.2009),
    )
    assert abs(prof.split.train_frac + prof.split.cal_frac
              + prof.split.test_frac - 1.0) <= 0.001


def test_output_precision_must_be_nonnegative():
    with pytest.raises(ValueError, match="precision"):
        _legacy_profile(output=OutputSpec(precision=-1))


def test_v05_profile_must_have_both_downloader_and_loader():
    """Setting only one of `downloader`/`loader` is invalid (the
    framework requires both for the v0.5 dispatch path)."""
    with pytest.raises(ValueError, match="missing data-source"):
        Profile(
            name="t", version="0.0", description="t",
            label=LabelSpec(source_column="label"),
            pipeline=[], split=SplitSpec(), output=OutputSpec(),
            loader="iot23",
            downloader=None,           # missing → invalid
            cached_at="raw/t/",
            source=None,
        )


def test_cannot_mix_v05_and_legacy_schemas():
    with pytest.raises(ValueError, match="not both"):
        Profile(
            name="t", version="0.0", description="t",
            label=LabelSpec(source_column="label"),
            pipeline=[], split=SplitSpec(), output=OutputSpec(),
            downloader="iot23",
            loader="iot23",
            cached_at="raw/t/",
            source=SourceSpec(kind="manual"),
        )


def test_must_declare_some_data_source():
    with pytest.raises(ValueError, match="missing data-source"):
        Profile(
            name="t", version="0.0", description="t",
            label=LabelSpec(source_column="label"),
            pipeline=[], split=SplitSpec(), output=OutputSpec(),
            downloader=None, loader=None, source=None,
        )


# ---------------------------------------------------------------------------
# load_profile (YAML)
# ---------------------------------------------------------------------------

def test_load_profile_v05_roundtrip(tmp_path):
    yaml = """
name: tinyset
version: 1.0.0
description: synthetic tinyset for schema tests
downloader: iot23
loader: iot23
cached_at: raw/tinyset/
loader_options:
  per_file_cap: 100
label:
  source_column: detailed-label
  rename_to: label
  normalize: lowercase_underscore
pipeline:
  - op: drop_columns
    columns: [ts, uid]
  - op: filter_min_class_count
    min_count: 50
split:
  kind: stratified_class_balanced
  train_frac: 0.6
  cal_frac:   0.2
  test_frac:  0.2
  seed: 42
output:
  format: csv
  precision: 6
  column_sort: alphabetical
  row_shuffle_seed: 42
expected_hashes:
  train.csv: abc123
"""
    p = tmp_path / "tinyset.yaml"
    p.write_text(yaml)
    prof = load_profile(p)

    assert prof.name == "tinyset"
    assert prof.loader == "iot23"
    assert prof.downloader == "iot23"
    assert prof.cached_at == "raw/tinyset/"
    assert prof.loader_options == {"per_file_cap": 100}
    assert prof.label.source_column == "detailed-label"
    assert prof.label.rename_to == "label"
    assert len(prof.pipeline) == 2
    assert prof.pipeline[0].op == "drop_columns"
    assert prof.pipeline[0].params == {"columns": ["ts", "uid"]}
    assert prof.split.train_frac == 0.6
    assert prof.split.seed == 42
    assert prof.expected_hashes == {"train.csv": "abc123"}
    assert prof.source_path == p.expanduser().resolve()


def test_load_profile_legacy_roundtrip(tmp_path):
    yaml = """
name: legacy_t
version: 1.0.0
description: legacy schema test
source:
  kind: openml
  name: pendigits
  cached_at: raw/legacy_t/
label:
  source_column: label
pipeline:
  - op: filter_min_class_count
    min_count: 10
split:
  train_frac: 0.5
  cal_frac:   0.25
  test_frac:  0.25
output: {}
"""
    p = tmp_path / "legacy.yaml"
    p.write_text(yaml)
    prof = load_profile(p)
    assert prof.source is not None
    assert prof.source.kind == "openml"
    assert prof.source.name == "pendigits"
    assert prof.loader is None
    assert prof.downloader is None


def test_load_profile_raises_on_missing_required_field(tmp_path):
    """The top-level required fields are name/version/description/label/pipeline."""
    yaml = """
version: 1.0.0
description: no name
label:
  source_column: label
pipeline: []
source:
  kind: manual
"""
    p = tmp_path / "broken.yaml"
    p.write_text(yaml)
    with pytest.raises(ValueError, match="missing required top-level field 'name'"):
        load_profile(p)


def test_load_profile_raises_on_missing_data_source(tmp_path):
    yaml = """
name: x
version: 1.0
description: missing source
label:
  source_column: label
pipeline: []
"""
    p = tmp_path / "no_source.yaml"
    p.write_text(yaml)
    with pytest.raises(ValueError, match="declare either"):
        load_profile(p)


def test_load_profile_raises_on_missing_label_source_column(tmp_path):
    yaml = """
name: x
version: 1.0
description: t
label: {}
pipeline: []
source:
  kind: manual
"""
    p = tmp_path / "no_label.yaml"
    p.write_text(yaml)
    with pytest.raises(ValueError, match="source_column"):
        load_profile(p)


def test_load_profile_raises_on_missing_pipeline_op(tmp_path):
    yaml = """
name: x
version: 1.0
description: t
label:
  source_column: label
pipeline:
  - columns: [a, b]                 # missing 'op'
source:
  kind: manual
"""
    p = tmp_path / "no_op.yaml"
    p.write_text(yaml)
    with pytest.raises(ValueError, match="missing required field 'op'"):
        load_profile(p)


def test_load_profile_file_not_found():
    with pytest.raises(FileNotFoundError, match="profile not found"):
        load_profile("/nonexistent/path/foo.yaml")


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

def test_split_spec_defaults():
    s = SplitSpec()
    assert s.train_frac == 0.6
    assert s.cal_frac == 0.2
    assert s.test_frac == 0.2
    assert s.seed == 42
    assert s.kind == "stratified_class_balanced"


def test_output_spec_defaults():
    o = OutputSpec()
    assert o.format == "csv"
    assert o.precision == 6
    assert o.column_sort == "alphabetical"
    assert o.row_shuffle_seed == 42


def test_label_spec_defaults():
    label = LabelSpec(source_column="raw")
    assert label.rename_to == "label"
    assert label.normalize == "lowercase_underscore"
