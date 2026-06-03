"""End-to-end pipeline executor: source → ops → split → canonical write."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tabprep.core.canonical import write_canonical_csv
from tabprep.core.manifest import build_manifest, write_manifest
from tabprep.core.profile import Profile
from tabprep.core.splits import run_split


def _load_source(profile: Profile) -> tuple[pd.DataFrame, str]:
    """Read raw bytes for `profile`, dispatching by schema version.

    v0.5: profile carries top-level `loader: <name>` → look up in
    `tabprep.datasets.LOADER_REGISTRY` and instantiate.
    v0.4: profile carries `source: { kind: ... }` → look up in
    `tabprep.sources.SOURCE_REGISTRY` (legacy path, retained until
    every built-in profile is migrated to v0.5).
    """
    label_col = profile.label.rename_to

    if profile.loader is not None:
        # v0.5 path. Importing tabprep.datasets triggers the package
        # walker which registers every dataset's @loader/@downloader.
        from tabprep.datasets import LOADER_REGISTRY
        cls = LOADER_REGISTRY.get(profile.loader)
        if cls is None:
            raise ValueError(
                f"unknown loader {profile.loader!r} "
                f"(registered: {sorted(LOADER_REGISTRY)})"
            )
        if profile.cached_at is None:
            raise ValueError(
                f"profile {profile.name!r}: loader requires `cached_at` to be set"
            )
        return cls().load(
            Path(profile.cached_at),
            label_col,
            **(profile.loader_options or {}),
        )

    # v0.4 legacy path.
    if profile.source is None:
        raise ValueError(f"profile {profile.name!r}: no loader or source declared")
    from tabprep.sources import SOURCE_REGISTRY
    fn = SOURCE_REGISTRY.get(profile.source.kind)
    if fn is None:
        raise ValueError(
            f"unknown source kind {profile.source.kind!r} "
            f"(registered: {sorted(SOURCE_REGISTRY)})"
        )
    df, label_col = fn(profile.source, label_col)
    return df, label_col


def _apply_pipeline(df: pd.DataFrame, profile: Profile,
                    label_col: str) -> pd.DataFrame:
    from tabprep.ops import OP_REGISTRY

    cur = df

    # The label-handling ops (rename + normalize) are applied implicitly
    # at the start so user pipelines don't have to repeat them on every
    # profile. The user can still override via explicit `rename_label` /
    # `normalize_label_string` ops in their pipeline if they want a
    # different order.
    if profile.label.source_column != profile.label.rename_to:
        cur = OP_REGISTRY["rename_label"](
            cur, label_col=label_col,
            source_column=profile.label.source_column,
            rename_to=profile.label.rename_to,
        )
    cur = OP_REGISTRY["normalize_label_string"](
        cur, label_col=label_col, method=profile.label.normalize
    )

    # Drop sibling target columns (the labels the profile did NOT pick) so
    # they cannot leak the answer into the features. Done structurally here
    # — not as an opt-in pipeline op — so a profile author can never forget
    # it. The chosen label_col is guarded out in case it is listed.
    extra = [c for c in profile.label.also_drop if c != label_col]
    if extra:
        cur = OP_REGISTRY["drop_columns"](cur, label_col=label_col, columns=extra)

    for spec in profile.pipeline:
        fn = OP_REGISTRY.get(spec.op)
        if fn is None:
            raise ValueError(
                f"unknown op {spec.op!r} (registered: {sorted(OP_REGISTRY)})"
            )
        cur = fn(cur, label_col=label_col, **spec.params)

    return cur


def run_pipeline(profile: Profile, output_root: str | Path) -> dict:
    """Execute a profile end-to-end and return a summary dict.

    Side-effect: writes `train.csv`, `calibration.csv`, `test.csv`, and
    `_manifest.json` under `output_root / profile.name /`.
    """
    out_dir = Path(output_root).expanduser() / profile.name
    out_dir.mkdir(parents=True, exist_ok=True)

    df, label_col = _load_source(profile)
    df = _apply_pipeline(df, profile, label_col)

    train, cal, test = run_split(
        df,
        label_col=label_col,
        kind=profile.split.kind,
        train_frac=profile.split.train_frac,
        cal_frac=profile.split.cal_frac,
        test_frac=profile.split.test_frac,
        seed=profile.split.seed,
    )

    files: list[Path] = []
    shapes: dict[Path, tuple[int, int]] = {}
    for name, frame in (("train.csv", train), ("calibration.csv", cal), ("test.csv", test)):
        out_path = out_dir / name
        write_canonical_csv(
            frame,
            out_path,
            precision=profile.output.precision,
            column_sort=profile.output.column_sort,
            row_shuffle_seed=profile.output.row_shuffle_seed,
        )
        files.append(out_path)
        shapes[out_path] = (len(frame), len(frame.columns))

    manifest = build_manifest(
        profile_name=profile.name,
        profile_version=profile.version,
        profile_path=profile.source_path or Path("<unknown>"),
        files=files,
        shapes=shapes,
    )
    manifest_path = out_dir / "_manifest.json"
    write_manifest(manifest, manifest_path)

    return {
        "out_dir": str(out_dir),
        "files": [{"path": e.path, "sha256": e.sha256, "rows": e.rows,
                   "cols": e.cols, "bytes": e.bytes}
                  for e in manifest.files],
        "manifest_path": str(manifest_path),
    }
