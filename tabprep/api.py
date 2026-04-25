"""Public Python API for tabprep.

Designed for one-call ergonomics:

    >>> import tabprep
    >>> result = tabprep.prepare("pendigits")
    >>> train_df, cal_df, test_df = result.load_all()

For notebooks where you want a DataFrame in one line and don't care
about the intermediate CSVs:

    >>> train_df, cal_df, test_df = tabprep.load_splits("pendigits")

A custom profile YAML works the same way:

    >>> result = tabprep.prepare("./my_profile.yaml", output_dir="out/")

Or skip the cleaning pipeline to inspect raw loader output (the implicit
label rename + normalize is still applied so the label column is
consistent):

    >>> train_df = tabprep.load_split("pendigits", split="train", skip_pipeline=True)

The CLI (`python -m tabprep prepare ...`) and this module are parallel
entry points into the same pipeline; either gives byte-identical
results when called with equivalent arguments.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from tabprep.core.hashing import canonical_sha256_of_file
from tabprep.core.pipeline import run_pipeline
from tabprep.core.profile import Profile, load_profile

ProfileSpec = Union[str, Path, Profile]
"""Three accepted forms for the `profile` argument:

  * **builtin name** (`str` like `"pendigits"`): looked up under the
    package's `tabprep/profiles/` dir, with a fall-through to legacy
    `tabprep/profiles/builtin/`.
  * **filesystem path** (`str` ending in `.yaml`/`.yml`, or any `Path`):
    loaded directly via `load_profile`.
  * **`Profile` instance**: returned as-is. Use this for fully
    programmatic profiles built without writing YAML to disk.
"""

DEFAULT_OUTPUT_DIR = Path("prepared")
DEFAULT_DATA_ROOT = Path(".")


@dataclass
class PrepareResult:
    """Outcome of a `prepare()` call.

    Attributes:
        profile: The resolved Profile that ran.
        output_dir: Directory holding the three split CSVs and manifest.
        train, calibration, test: Paths to the canonical split CSVs.
        manifest_path: Path to `_manifest.json`.
        sha256: Mapping of `filename → sha256_hex`.
        verified: `True` if every pinned `expected_hashes` matched,
            `False` if any mismatched, `None` if the profile didn't
            pin any hashes.
    """
    profile: Profile
    output_dir: Path
    train: Path
    calibration: Path
    test: Path
    manifest_path: Path
    sha256: dict[str, str]
    verified: Optional[bool]

    def load(self, split: str = "train") -> pd.DataFrame:
        """Read one split — `"train"`, `"calibration"` (or `"cal"`), or `"test"`."""
        path = {
            "train": self.train,
            "calibration": self.calibration,
            "cal": self.calibration,
            "test": self.test,
        }.get(split)
        if path is None:
            raise ValueError(
                f"unknown split {split!r} (expected train/calibration/cal/test)"
            )
        return pd.read_csv(path)

    def load_all(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Read all three splits — returns `(train, calibration, test)`."""
        return self.load("train"), self.load("calibration"), self.load("test")


# ---------------------------------------------------------------------------
# Profile resolution
# ---------------------------------------------------------------------------

def _profiles_root() -> Path:
    """Path to the bundled profiles directory inside the package.

    `__file__` is `<install>/tabprep/api.py` for both editable
    (`pip install -e .`) and standard (`pip install .`) installs, so
    `.parent / "profiles"` resolves to `<install>/tabprep/profiles/`,
    which ships with the package via `pyproject.toml`'s
    `[tool.setuptools.package-data]` glob.
    """
    return Path(__file__).parent / "profiles"


def resolve_profile(profile: ProfileSpec) -> Profile:
    """Coerce a `ProfileSpec` to a `Profile`.

    A bare name (no path separators, no `.yaml` suffix) is treated as a
    built-in lookup; anything else is loaded as a filesystem path. A
    `Profile` instance is returned unchanged.

    Built-in lookup tries (in order) `tabprep/profiles/<name>.yaml` and
    `tabprep/profiles/builtin/<name>.yaml` (the latter is a transitional
    location for unmigrated v0.4 profiles).
    """
    if isinstance(profile, Profile):
        return profile

    if isinstance(profile, Path):
        return load_profile(profile)

    if not isinstance(profile, str):
        raise TypeError(
            f"profile must be str | Path | Profile (got {type(profile).__name__})"
        )

    looks_like_path = (
        any(sep in profile for sep in ("/", "\\"))
        or profile.endswith((".yaml", ".yml"))
    )
    if looks_like_path:
        return load_profile(profile)

    root = _profiles_root()
    candidates = [root / f"{profile}.yaml", root / "builtin" / f"{profile}.yaml"]
    for c in candidates:
        if c.is_file():
            return load_profile(c)

    available = sorted(p.stem for p in root.glob("*.yaml"))
    available += sorted(p.stem for p in (root / "builtin").glob("*.yaml")
                        if p.stem not in available)
    raise FileNotFoundError(
        f"no built-in profile named {profile!r}. "
        f"Available: {', '.join(available)}. "
        f"To use a custom profile, pass a path: "
        f"tabprep.prepare('/path/to/my_profile.yaml')"
    )


def list_profiles() -> list[Profile]:
    """List every built-in profile, parsed and validated.

    Profiles in `tabprep/profiles/` (v0.5 layout) shadow same-named ones
    in `tabprep/profiles/builtin/` (legacy v0.4 layout); each profile
    appears once.
    """
    root = _profiles_root()
    seen: dict[str, Path] = {}
    for d in (root, root / "builtin"):
        if d.is_dir():
            for p in sorted(d.glob("*.yaml")):
                if p.stem not in seen:
                    seen[p.stem] = p

    out: list[Profile] = []
    for path in sorted(seen.values(), key=lambda p: p.stem):
        try:
            out.append(load_profile(path))
        except Exception:                                                  # noqa: BLE001
            continue
    return out


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------

def _resolve_cached_at(profile: Profile, data_root: Path) -> None:
    """Resolve relative `cached_at` to absolute against `data_root`. Mutates."""
    if profile.loader is not None and profile.cached_at:
        cached = Path(profile.cached_at)
        if not cached.is_absolute():
            profile.cached_at = str((data_root / cached).resolve())
    elif profile.source is not None and profile.source.cached_at:
        cached = Path(profile.source.cached_at)
        if not cached.is_absolute():
            profile.source.cached_at = str((data_root / cached).resolve())


def _ensure_cached(profile: Profile) -> None:
    """Trigger any auto-download declared by the profile (idempotent)."""
    if profile.loader is not None:
        if not profile.cached_at or profile.downloader is None:
            return
        from tabprep.datasets import DOWNLOADER_REGISTRY
        cls = DOWNLOADER_REGISTRY.get(profile.downloader)
        if cls is None:
            raise ValueError(
                f"unknown downloader {profile.downloader!r} "
                f"(registered: {sorted(DOWNLOADER_REGISTRY)})"
            )
        cls().download(Path(profile.cached_at))
        return

    # Legacy `source:` block.
    src = profile.source
    if src is None or not src.cached_at:
        return
    urls: list[str] = []
    if src.download_url:
        urls.append(src.download_url)
    if src.download_urls:
        urls.extend(src.download_urls)
    if not urls:
        return
    from tabprep.core.downloader import derive_target_name, download_and_extract
    cached = Path(src.cached_at)
    for u in urls:
        target = derive_target_name(u) if len(urls) > 1 else None
        download_and_extract(
            u, cached,
            archive_format=src.archive_format,
            expected_sha256=src.download_sha256 if len(urls) == 1 else None,
            target_name=target,
        )


def prepare(
    profile: ProfileSpec,
    output_dir: Optional[Union[str, Path]] = None,
    *,
    data_root: Optional[Union[str, Path]] = None,
    skip_pipeline: bool = False,
    quiet: bool = False,
) -> PrepareResult:
    """Prepare a dataset end-to-end and return a `PrepareResult`.

    The pipeline runs **download → load → clean → split → canonical-write
    → manifest**, mirroring the CLI's `tabprep prepare` exactly. Output
    bytes are deterministic across runs, so calling `prepare()` twice
    with the same arguments produces identical files.

    Args:
        profile: Built-in name (`"pendigits"`), path to a YAML file, or
            a `Profile` instance.
        output_dir: Where to write outputs. Defaults to `./prepared`.
            Final destination is `output_dir / <profile_name> / *.csv`.
        data_root: Root for relative `cached_at` paths. Defaults to the
            current working directory.
        skip_pipeline: When `True`, skip the user-defined cleaning ops
            (drop_columns, encode_categoricals, fill_nan, etc.). The
            implicit label rename + normalize still runs so the output
            label column is consistent. **Note**: pinned
            `expected_hashes` will not match in this mode — the result's
            `verified` field will be `False`.
        quiet: Suppress progress prints (default: `False`).

    Returns:
        `PrepareResult` with paths, sha256s, and verification status.

    Examples:
        >>> import tabprep
        >>> result = tabprep.prepare("pendigits")
        >>> result.verified
        True
        >>> train_df = result.load("train")

        Custom output dir + custom profile YAML:

        >>> result = tabprep.prepare("./my_profile.yaml",
        ...                          output_dir="./out")
    """
    prof = resolve_profile(profile)
    # Defensive shallow copy so we don't mutate a Profile the caller may
    # still hold a reference to: prepare() resolves `cached_at` to an
    # absolute path in-place, and `dataclasses.replace` below for
    # `skip_pipeline=True` would otherwise also mutate `pipeline`.
    prof = dataclasses.replace(prof)
    out_root = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    data_root_p = Path(data_root) if data_root is not None else DEFAULT_DATA_ROOT

    _resolve_cached_at(prof, data_root_p)

    if not quiet:
        print(f"[tabprep] prepare {prof.name} v{prof.version}")
        if prof.loader is not None:
            print(f"          downloader: {prof.downloader}  loader: {prof.loader}")
            if prof.cached_at:
                print(f"          cached_at: {prof.cached_at}")
        elif prof.source is not None:
            print(f"          source: kind={prof.source.kind} name={prof.source.name}")
        print(f"          output: {(out_root / prof.name).resolve()}")
        if skip_pipeline:
            print("          [info] skip_pipeline=True — user pipeline ops bypassed")

    _ensure_cached(prof)

    profile_to_run = (
        dataclasses.replace(prof, pipeline=[]) if skip_pipeline else prof
    )
    summary = run_pipeline(profile_to_run, output_root=out_root)

    out_dir = out_root / prof.name
    sha256s = {f["path"]: f["sha256"] for f in summary["files"]}

    verified: Optional[bool] = None
    if prof.expected_hashes:
        verified = all(
            sha256s.get(fname) == expected
            for fname, expected in prof.expected_hashes.items()
        )

    if not quiet:
        for f in summary["files"]:
            print(f"  {f['path']:<18} sha256={f['sha256'][:12]}…  "
                  f"rows={f['rows']}  cols={f['cols']}")
        if verified is True:
            print("[ok] expected_hashes match — fully reproduced.")
        elif verified is False:
            print("[warn] expected_hashes mismatch — output differs from "
                  "the pinned recipe. (Expected with skip_pipeline=True.)")

    return PrepareResult(
        profile=prof,
        output_dir=out_dir,
        train=out_dir / "train.csv",
        calibration=out_dir / "calibration.csv",
        test=out_dir / "test.csv",
        manifest_path=Path(summary["manifest_path"]),
        sha256=sha256s,
        verified=verified,
    )


# ---------------------------------------------------------------------------
# load_splits / load_split
# ---------------------------------------------------------------------------

def _cache_is_valid(profile: Profile, out_dir: Path) -> bool:
    """True if `out_dir` has all 3 split CSVs and (if pinned) the
    hashes match `profile.expected_hashes`. When no hashes are pinned,
    file existence is sufficient.
    """
    needed = ("train.csv", "calibration.csv", "test.csv")
    for fname in needed:
        if not (out_dir / fname).is_file():
            return False
    if not profile.expected_hashes:
        return True
    for fname, expected in profile.expected_hashes.items():
        path = out_dir / fname
        if not path.is_file():
            return False
        if canonical_sha256_of_file(path) != expected:
            return False
    return True


def load_splits(
    profile: ProfileSpec,
    *,
    output_dir: Optional[Union[str, Path]] = None,
    data_root: Optional[Union[str, Path]] = None,
    skip_pipeline: bool = False,
    use_cache: bool = True,
    quiet: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One-call: prepare (cached if possible) and return `(train, cal, test)`.

    With `use_cache=True` (the default), if the output directory already
    contains the three split CSVs and their pinned hashes match (or no
    hashes are pinned), preparation is skipped and the existing files
    are read directly. This makes repeated calls in notebooks fast.

    Args:
        profile: Built-in name, YAML path, or `Profile`.
        output_dir: Where CSVs are read from / written to. Defaults to `./prepared`.
        data_root: Root for relative `cached_at` paths. Defaults to cwd.
        skip_pipeline: Forwarded to `prepare()`. Note that with
            `use_cache=True`, an existing cached output (built without
            skip_pipeline) is reused regardless of this flag — set
            `use_cache=False` to force a rebuild.
        use_cache: When `True` (default), reuse cached CSVs if their
            hashes match (or no hashes are pinned).
        quiet: Suppress prepare's progress prints (default: `True`,
            since the convenience function should feel passive).

    Returns:
        `(train_df, calibration_df, test_df)` — three `pd.DataFrame`s.

    Example:
        >>> import tabprep
        >>> train_df, cal_df, test_df = tabprep.load_splits("pendigits")
    """
    prof = resolve_profile(profile)
    out_root = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    out_dir = out_root / prof.name

    if use_cache and _cache_is_valid(prof, out_dir):
        return (
            pd.read_csv(out_dir / "train.csv"),
            pd.read_csv(out_dir / "calibration.csv"),
            pd.read_csv(out_dir / "test.csv"),
        )

    result = prepare(
        prof,
        output_dir=out_root,
        data_root=data_root,
        skip_pipeline=skip_pipeline,
        quiet=quiet,
    )
    return result.load_all()


def load_split(
    profile: ProfileSpec,
    split: str = "train",
    *,
    output_dir: Optional[Union[str, Path]] = None,
    data_root: Optional[Union[str, Path]] = None,
    skip_pipeline: bool = False,
    use_cache: bool = True,
    quiet: bool = True,
) -> pd.DataFrame:
    """Convenience: prepare (cached if possible) and return one split.

    `split` is one of `"train"`, `"calibration"` (or `"cal"`), `"test"`.
    See `load_splits()` for details on the other arguments.
    """
    train, cal, test = load_splits(
        profile,
        output_dir=output_dir,
        data_root=data_root,
        skip_pipeline=skip_pipeline,
        use_cache=use_cache,
        quiet=quiet,
    )
    by_name = {"train": train, "calibration": cal, "cal": cal, "test": test}
    if split not in by_name:
        raise ValueError(
            f"unknown split {split!r} (expected train/calibration/cal/test)"
        )
    return by_name[split]
