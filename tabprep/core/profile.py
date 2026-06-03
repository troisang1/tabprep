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
    """Where to fetch the raw data.

    Two URL fields:
      - `url`           — landing/info page (informational; may also serve
                          as a free-form metadata slot for legacy profiles
                          that overload it for encoding / glob hints).
      - `download_url`  — direct fetch URL the auto-downloader uses; if
                          set and `cached_at` is empty, `tabprep prepare`
                          fetches and extracts before running the
                          pipeline.

    For form-gated datasets (e.g. CIC), leave `download_url` unset and
    document the manual-download steps in the profile description; the
    framework will then surface a helpful FileNotFoundError pointing the
    user at `url` for the licence form.
    """
    kind: str                                  # url | sklearn | openml | concat_csvs | nbaiot_dir | zeek_conn_log | manual
    name: str | None = None                    # sklearn / openml dataset key
    url: str | None = None                     # landing page or legacy metadata
    sha256: str | None = None                  # raw-file integrity check (single-file sources)
    cached_at: str | None = None               # local relative path under data/raw/
    download_url: str | None = None            # direct fetch URL for auto-download (single file/archive)
    download_urls: list[str] | None = None     # multiple URLs (e.g. UNSW-NB15's 4 separate CSVs) — alternative to download_url
    download_sha256: str | None = None         # verifies the downloaded archive bytes (single-URL only)
    archive_format: str | None = None          # tar.gz | tgz | tar | zip | gz | none — auto-detected from URL when None
    encoding: str | None = None                # CSV encoding hint for concat_csvs (utf-8 | latin-1 | cp1252)
    glob: str | None = None                    # file-discovery pattern + options for zeek_conn_log (e.g. "*.labeled|per_file_cap=50000")


@dataclass
class LabelSpec:
    """How to identify the target column.

    `also_drop` lists *other* label/target columns to remove. IDS datasets
    routinely ship several mutually-derived targets (e.g. Bot-IoT has
    `attack`/`category`/`subcategory`; CIC-APT-IIoT has
    `label`/`subLabel`/`subLabelCat`). The profile picks one as the target
    via `source_column`; every sibling target named here is dropped before
    the pipeline runs so it cannot leak the answer into the feature set.
    (A pre-existing column literally named `rename_to` is dropped by
    `rename_label` automatically and need not be listed.)
    """
    source_column: str                         # column name in the raw dataset
    rename_to: str = "label"
    normalize: str = "lowercase_underscore"    # lowercase_underscore | none
    also_drop: list[str] = field(default_factory=list)  # sibling target columns to drop


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
    label: LabelSpec
    pipeline: list[OpSpec]
    split: SplitSpec
    output: OutputSpec
    # v0.5: top-level downloader/loader vocabulary. Both fields are
    # short names that look up classes in the dataset registries
    # (`tabprep.datasets._base.DOWNLOADER_REGISTRY` /
    # `LOADER_REGISTRY`). When both are set, the new dispatch path
    # is used; otherwise the legacy `source:` block is required.
    downloader: str | None = None
    loader: str | None = None
    cached_at: str | None = None
    loader_options: dict[str, Any] = field(default_factory=dict)
    # v0.4 legacy schema: a `source:` block carrying SourceSpec. Kept
    # functional through Phases 2-4 of the v0.5 migration so un-
    # migrated profiles continue to load.
    source: SourceSpec | None = None
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
        # Either the new dispatch (downloader+loader) OR the legacy
        # `source:` block must be specified — never both, never neither.
        new_set = self.downloader is not None and self.loader is not None
        legacy_set = self.source is not None
        if new_set and legacy_set:
            raise ValueError(
                "profile must use EITHER `downloader:`+`loader:` (v0.5) "
                "OR `source:` (legacy v0.4) — not both"
            )
        if not new_set and not legacy_set:
            raise ValueError(
                "profile missing data-source declaration: set either "
                "`downloader:`+`loader:` or `source:`"
            )


def _coerce_source(d: dict[str, Any]) -> SourceSpec:
    if "kind" not in d:
        raise ValueError("source: missing required field 'kind'")
    return SourceSpec(
        kind=str(d["kind"]),
        name=d.get("name"),
        url=d.get("url"),
        sha256=d.get("sha256"),
        cached_at=d.get("cached_at"),
        download_url=d.get("download_url"),
        download_urls=d.get("download_urls"),
        download_sha256=d.get("download_sha256"),
        archive_format=d.get("archive_format"),
        encoding=d.get("encoding"),
        glob=d.get("glob"),
    )


def _coerce_label(d: dict[str, Any]) -> LabelSpec:
    if "source_column" not in d:
        raise ValueError("label: missing required field 'source_column'")
    return LabelSpec(
        source_column=str(d["source_column"]),
        rename_to=str(d.get("rename_to", "label")),
        normalize=str(d.get("normalize", "lowercase_underscore")),
        also_drop=[str(x) for x in (d.get("also_drop") or [])],
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
    """Read a YAML profile from disk and return a validated Profile.

    Supports two schemas:

      * **v0.5 (preferred)**: top-level `downloader:` + `loader:` keys
        plus `cached_at:` and an optional `loader_options:` dict.
      * **v0.4 (legacy)**: a `source:` block with `kind`, `cached_at`,
        download URLs, encoding/glob hints. Honoured through the v0.5
        migration phases so un-migrated profiles continue to load.

    Each profile must use exactly one of the two — `Profile.__post_init__`
    enforces this.
    """
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(f"profile not found: {p}")

    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    for key in ("name", "version", "description", "label", "pipeline"):
        if key not in raw:
            raise ValueError(f"{p.name}: missing required top-level field '{key}'")

    has_new_schema = "downloader" in raw or "loader" in raw
    has_legacy_schema = "source" in raw
    if not has_new_schema and not has_legacy_schema:
        raise ValueError(f"{p.name}: must declare either `downloader:`+`loader:` "
                         f"(v0.5) or `source:` (legacy v0.4)")

    profile = Profile(
        name=str(raw["name"]),
        version=str(raw["version"]),
        description=str(raw["description"]),
        label=_coerce_label(raw["label"]),
        pipeline=_coerce_pipeline(raw.get("pipeline", [])),
        split=_coerce_split(raw.get("split")),
        output=_coerce_output(raw.get("output")),
        # v0.5 fields:
        downloader=raw.get("downloader"),
        loader=raw.get("loader"),
        cached_at=raw.get("cached_at"),
        loader_options=dict(raw.get("loader_options") or {}),
        # legacy:
        source=_coerce_source(raw["source"]) if has_legacy_schema else None,
        expected_hashes=dict(raw.get("expected_hashes", {})),
    )
    profile.source_path = p
    return profile
