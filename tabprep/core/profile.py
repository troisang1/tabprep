"""Profile YAML loader + lightweight schema validation.

A Profile is the declarative description of how to go from a raw source
to ready-to-use train/calibration/test CSVs. It carries:

  * `source`        — where the raw data comes from
  * `label`         — how to identify and normalise the target column
  * `pipeline`      — ordered list of cleaning / encoding ops
  * `split`         — train/cal/test split parameters
  * `output`        — canonical-write parameters (precision, sort)
  * `expected_hashes` (optional) — sha256 fingerprints of the outputs

This module deliberately uses dataclasses + manual validation rather than
pydantic to keep the dependency tree small.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Default split fractions match the cnNFST convention (60/20/20). These
# are overridable in any profile via the `split:` block.
DEFAULT_TRAIN_FRAC = 0.6
DEFAULT_CAL_FRAC = 0.2
DEFAULT_TEST_FRAC = 0.2
DEFAULT_SEED = 42


@dataclass
class SourceSpec:
    """Where to fetch the raw data."""
    kind: str                                  # url | sklearn | openml | manual
    name: str | None = None                    # sklearn / openml dataset key
    url: str | None = None
    sha256: str | None = None                  # raw-file integrity check
    cached_at: str | None = None               # local relative path under data/raw/


@dataclass
class LabelSpec:
    """How to identify the target column."""
    source_column: str                         # column name in the raw dataset
    rename_to: str = "label"
    normalize: str = "lowercase_underscore"    # lowercase_underscore | none


@dataclass
class OpSpec:
    """One node in the preprocessing pipeline."""
    op: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitSpec:
    """Train / calibration / test split parameters."""
    kind: str = "stratified_class_balanced"
    train_frac: float = DEFAULT_TRAIN_FRAC
    cal_frac: float = DEFAULT_CAL_FRAC
    test_frac: float = DEFAULT_TEST_FRAC
    seed: int = DEFAULT_SEED


@dataclass
class OutputSpec:
    """Canonical-write parameters for byte-stable output CSVs."""
    format: str = "csv"
    precision: int = 6                         # decimal places for floats
    column_sort: str = "alphabetical"          # alphabetical | source_order
    row_shuffle_seed: int = DEFAULT_SEED


@dataclass
class Profile:
    name: str
    version: str
    description: str
    source: SourceSpec
    label: LabelSpec
    pipeline: list[OpSpec]
    split: SplitSpec
    output: OutputSpec
    expected_hashes: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None            # filled by load_profile

    def __post_init__(self) -> None:
        # Sanity checks; raise on inconsistency so users see it at load time.
        s = self.split
        total = s.train_frac + s.cal_frac + s.test_frac
        if not 0.999 <= total <= 1.001:
            raise ValueError(
                f"split fractions must sum to 1.0 (got "
                f"{s.train_frac}+{s.cal_frac}+{s.test_frac}={total:.4f})"
            )
        if self.output.precision < 0:
            raise ValueError("output.precision must be >= 0")


def _coerce_source(d: dict[str, Any]) -> SourceSpec:
    if "kind" not in d:
        raise ValueError("source: missing required field 'kind'")
    return SourceSpec(
        kind=str(d["kind"]),
        name=d.get("name"),
        url=d.get("url"),
        sha256=d.get("sha256"),
        cached_at=d.get("cached_at"),
    )


def _coerce_label(d: dict[str, Any]) -> LabelSpec:
    if "source_column" not in d:
        raise ValueError("label: missing required field 'source_column'")
    return LabelSpec(
        source_column=str(d["source_column"]),
        rename_to=str(d.get("rename_to", "label")),
        normalize=str(d.get("normalize", "lowercase_underscore")),
    )


def _coerce_pipeline(items: list[dict[str, Any]]) -> list[OpSpec]:
    out: list[OpSpec] = []
    for i, raw in enumerate(items or []):
        if "op" not in raw:
            raise ValueError(f"pipeline[{i}]: missing required field 'op'")
        params = {k: v for k, v in raw.items() if k != "op"}
        out.append(OpSpec(op=str(raw["op"]), params=params))
    return out


def _coerce_split(d: dict[str, Any] | None) -> SplitSpec:
    d = d or {}
    return SplitSpec(
        kind=str(d.get("kind", "stratified_class_balanced")),
        train_frac=float(d.get("train_frac", DEFAULT_TRAIN_FRAC)),
        cal_frac=float(d.get("cal_frac", DEFAULT_CAL_FRAC)),
        test_frac=float(d.get("test_frac", DEFAULT_TEST_FRAC)),
        seed=int(d.get("seed", DEFAULT_SEED)),
    )


def _coerce_output(d: dict[str, Any] | None) -> OutputSpec:
    d = d or {}
    return OutputSpec(
        format=str(d.get("format", "csv")),
        precision=int(d.get("precision", 6)),
        column_sort=str(d.get("column_sort", "alphabetical")),
        row_shuffle_seed=int(d.get("row_shuffle_seed", DEFAULT_SEED)),
    )


def load_profile(path: str | Path) -> Profile:
    """Read a YAML profile from disk and return a validated Profile."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"profile not found: {p}")

    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    for key in ("name", "version", "description", "source", "label", "pipeline"):
        if key not in raw:
            raise ValueError(f"{p.name}: missing required top-level field '{key}'")

    profile = Profile(
        name=str(raw["name"]),
        version=str(raw["version"]),
        description=str(raw["description"]),
        source=_coerce_source(raw["source"]),
        label=_coerce_label(raw["label"]),
        pipeline=_coerce_pipeline(raw.get("pipeline", [])),
        split=_coerce_split(raw.get("split")),
        output=_coerce_output(raw.get("output")),
        expected_hashes=dict(raw.get("expected_hashes", {})),
    )
    profile.source_path = p
    return profile
