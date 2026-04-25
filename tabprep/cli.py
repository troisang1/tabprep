"""tabprep CLI — `tabprep prepare|verify|list|init-profile`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tabprep import __version__
from tabprep.core.downloader import download_and_extract
from tabprep.core.hashing import canonical_sha256_of_file
from tabprep.core.pipeline import run_pipeline
from tabprep.core.profile import Profile, load_profile

# Defaults assume `tabprep` is run from its own project root (where
# `raw/` and `prepared/` are siblings of the package).
DEFAULT_OUTPUT_ROOT = Path("prepared")               # tabprep writes here
DEFAULT_DATA_ROOT = Path(".")                        # raw/ lives at the project root
# Profile lookup: bundled inside the package so `pip install tabprep`
# ships the YAMLs (see `pyproject.toml`'s package_data glob). v0.5
# profiles live in `tabprep/profiles/`; unmigrated v0.4 profiles live
# under `tabprep/profiles/builtin/` until Phase 4 finishes.
_PROFILE_DIRS = (
    Path(__file__).parent / "profiles",
    Path(__file__).parent / "profiles" / "builtin",
)


def _builtin_profiles() -> list[Path]:
    """Walk the candidate profile dirs and return every `*.yaml`.

    A profile that lives in both `tabprep/profiles/<name>.yaml` (v0.5
    layout) and `tabprep/profiles/builtin/<name>.yaml` (v0.4 legacy) —
    which can happen mid-migration — is reported only once, with the
    v0.5 path winning.
    """
    seen: dict[str, Path] = {}
    for d in _PROFILE_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.yaml")):
            if p.stem not in seen:
                seen[p.stem] = p
    return sorted(seen.values(), key=lambda p: p.stem)


def _filter_profiles(paths: list[Path], source_kinds: list[str] | None) -> list[Path]:
    if not source_kinds:
        return paths
    wanted = {k.strip().lower() for k in source_kinds}
    out: list[Path] = []
    for p in paths:
        try:
            prof = load_profile(p)
            if prof.source.kind.lower() in wanted:
                out.append(p)
        except Exception:                                              # noqa: BLE001
            continue
    return out


def cmd_list(args: argparse.Namespace) -> int:
    profiles = _builtin_profiles()
    if not profiles:
        print("(no built-in profiles found)")
        return 0
    print(f"Built-in profiles ({len(profiles)}):")
    for p in profiles:
        try:
            prof = load_profile(p)
            # Show only the first line of multi-line descriptions to keep
            # the list output one-row-per-profile.
            desc = (prof.description or "").splitlines()[0].strip()
            print(f"  {prof.name:<20} v{prof.version}   {desc}")
        except Exception as exc:                                      # noqa: BLE001
            print(f"  {p.name}: <invalid: {exc}>")
    return 0


def _ensure_cached(profile: Profile) -> None:
    """Trigger any auto-download declared by the profile.

    v0.5 path (`profile.downloader: <name>`): look up the registered
    `BaseDownloader` subclass, instantiate it, and call `download(cached_at)`.
    Form-gated downloaders raise with their refusal message.

    v0.4 legacy path (`profile.source.download_url(s)`): use the
    `download_and_extract` helper directly. Retained until every built-
    in profile is migrated.
    """
    if profile.loader is not None:
        # v0.5
        if not profile.cached_at:
            return
        if profile.downloader is None:
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

    # v0.4 legacy
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
    from tabprep.core.downloader import derive_target_name
    cached = Path(src.cached_at)
    for u in urls:
        target = derive_target_name(u) if len(urls) > 1 else None
        download_and_extract(
            u,
            cached,
            archive_format=src.archive_format,
            expected_sha256=src.download_sha256 if len(urls) == 1 else None,
            target_name=target,
        )


def _resolve_cached_at(profile: Profile, data_root: Path) -> None:
    """Resolve the profile's `cached_at` (v0.5) or `source.cached_at`
    (v0.4) to an absolute path against `--data-root` when it is given
    as a relative path. Mutates the profile in place.
    """
    if profile.loader is not None:
        if profile.cached_at:
            cached = Path(profile.cached_at)
            if not cached.is_absolute():
                profile.cached_at = str((data_root / cached).resolve())
    elif profile.source is not None and profile.source.cached_at:
        cached = Path(profile.source.cached_at)
        if not cached.is_absolute():
            profile.source.cached_at = str((data_root / cached).resolve())


def _prepare_one(profile: Profile, out_root: Path, data_root: Path) -> int:
    _resolve_cached_at(profile, data_root)
    print(f"[tabprep] prepare {profile.name} v{profile.version}")
    if profile.loader is not None:
        print(f"          downloader: {profile.downloader}  loader: {profile.loader}")
        if profile.cached_at:
            print(f"          cached_at: {profile.cached_at}")
    else:
        print(f"          source: kind={profile.source.kind} name={profile.source.name}")
        if profile.source.cached_at:
            print(f"          cached_at: {profile.source.cached_at}")
    print(f"          output: {out_root.resolve() / profile.name}")
    _ensure_cached(profile)
    summary = run_pipeline(profile, output_root=out_root)

    print("[ok] wrote files:")
    for f in summary["files"]:
        print(f"  {f['path']:<18} sha256={f['sha256'][:12]}…  "
              f"rows={f['rows']}  cols={f['cols']}  bytes={f['bytes']}")
    print(f"[ok] manifest: {summary['manifest_path']}")

    if profile.expected_hashes:
        bad = []
        for f in summary["files"]:
            expected = profile.expected_hashes.get(f["path"])
            if expected and expected != f["sha256"]:
                bad.append((f["path"], expected, f["sha256"]))
        if bad:
            print("[FAIL] expected_hashes mismatch:", file=sys.stderr)
            for p, exp, got in bad:
                print(f"  {p}: expected {exp[:12]}…  got {got[:12]}…", file=sys.stderr)
            return 1
        print("[ok] expected_hashes match — fully reproduced.")

    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    out_root = Path(args.output_root).expanduser()
    data_root = Path(args.data_root).expanduser()

    if args.all:
        kinds = args.source_kinds.split(",") if args.source_kinds else None
        targets = _filter_profiles(_builtin_profiles(), kinds)
        if not targets:
            print(f"[FAIL] no built-in profiles match --source-kinds={args.source_kinds}",
                  file=sys.stderr)
            return 1
        rc_total = 0
        for path in targets:
            print(f"\n══ {path.name} ══")
            try:
                profile = load_profile(path)
                rc = _prepare_one(profile, out_root, data_root)
            except Exception as exc:                                      # noqa: BLE001
                print(f"[FAIL] {path.name}: {exc}", file=sys.stderr)
                rc = 1
            rc_total |= rc
        return rc_total

    if not args.profile:
        print("[FAIL] specify --profile <path> or --all", file=sys.stderr)
        return 2
    return _prepare_one(load_profile(args.profile), out_root, data_root)


def _verify_one(profile: Profile, out_root: Path) -> int:
    if not profile.expected_hashes:
        print(f"[skip] {profile.name}: no expected_hashes in profile.")
        return 0
    out_dir = out_root / profile.name
    if not out_dir.is_dir():
        print(f"[FAIL] {profile.name}: no output dir at {out_dir} — "
              f"run `tabprep prepare` first.", file=sys.stderr)
        return 1

    bad = []
    for fname, expected in sorted(profile.expected_hashes.items()):
        f = out_dir / fname
        if not f.is_file():
            bad.append((fname, expected, "<missing>"))
            continue
        observed = canonical_sha256_of_file(f)
        if observed != expected:
            bad.append((fname, expected, observed))
    if bad:
        print(f"[FAIL] {profile.name}: hash mismatch on {len(bad)} file(s)",
              file=sys.stderr)
        for fname, exp, got in bad:
            print(f"  {fname}: expected {exp[:12]}…  got {got[:12]}…", file=sys.stderr)
        return 1
    print(f"[ok] {profile.name}: all {len(profile.expected_hashes)} files match.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    out_root = Path(args.output_root).expanduser()

    if args.all:
        kinds = args.source_kinds.split(",") if args.source_kinds else None
        targets = _filter_profiles(_builtin_profiles(), kinds)
        if not targets:
            print(f"[FAIL] no built-in profiles match --source-kinds={args.source_kinds}",
                  file=sys.stderr)
            return 1
        rc_total = 0
        n_ok = 0
        n_skip = 0
        for path in targets:
            try:
                profile = load_profile(path)
                rc = _verify_one(profile, out_root)
                if rc == 0:
                    n_ok += 1 if profile.expected_hashes else 0
                    n_skip += 0 if profile.expected_hashes else 1
                else:
                    rc_total |= rc
            except Exception as exc:                                      # noqa: BLE001
                print(f"[FAIL] {path.name}: {exc}", file=sys.stderr)
                rc_total |= 1
        print(f"\n[summary] verified {n_ok} / {len(targets)} profile(s) "
              f"(skipped {n_skip} without expected_hashes)")
        return rc_total

    if not args.profile:
        print("[FAIL] specify --profile <path> or --all", file=sys.stderr)
        return 2
    return _verify_one(load_profile(args.profile), out_root)


def cmd_download(args: argparse.Namespace) -> int:
    """Fetch + extract the raw data for a profile.

    v0.5: dispatches to `BaseDownloader.download(cached_at)`.
    v0.4: uses `download_and_extract` directly with `source.download_url`.
    """
    data_root = Path(args.data_root).expanduser()
    profile = load_profile(args.profile)
    _resolve_cached_at(profile, data_root)

    if profile.loader is not None:
        # v0.5
        if not profile.cached_at:
            print(f"[FAIL] {profile.name}: missing cached_at", file=sys.stderr)
            return 1
        if profile.downloader is None:
            print(f"[skip] {profile.name}: no downloader declared.\n"
                  f"  Place data under {profile.cached_at} manually.",
                  file=sys.stderr)
            return 2
        from tabprep.datasets import DOWNLOADER_REGISTRY
        cls = DOWNLOADER_REGISTRY.get(profile.downloader)
        if cls is None:
            print(f"[FAIL] unknown downloader {profile.downloader!r}", file=sys.stderr)
            return 1
        cls().download(Path(profile.cached_at))
        return 0

    # v0.4 legacy
    if profile.source is None or not profile.source.download_url:
        print(f"[skip] {profile.name}: no download_url in profile.",
              file=sys.stderr)
        return 2
    cached = Path(profile.source.cached_at) if profile.source.cached_at else None
    if cached is None:
        print(f"[FAIL] {profile.name}: missing cached_at", file=sys.stderr)
        return 1
    if not cached.is_absolute():
        cached = data_root / cached
    download_and_extract(
        profile.source.download_url,
        cached,
        archive_format=profile.source.archive_format,
        expected_sha256=profile.source.download_sha256,
        force=bool(args.force),
    )
    return 0


def cmd_init_profile(args: argparse.Namespace) -> int:
    """Stub — full implementation slated for v0.5."""
    print("[tabprep] init-profile is not yet implemented.\n"
          "  See README.md ('Authoring a custom profile') for the planned UX.\n"
          "  For now, copy tabprep/profiles/pendigits.yaml as a starting point\n"
          "  and edit the source/pipeline/split sections.",
          file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tabprep",
        description="Reproducible tabular dataset preparation.",
    )
    parser.add_argument("--version", action="version", version=f"tabprep {__version__}")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List built-in profiles.")
    p_list.set_defaults(func=cmd_list)

    p_prep = sub.add_parser("prepare", help="Run a profile end-to-end.")
    p_prep.add_argument("--profile", help="Path to a profile YAML.")
    p_prep.add_argument("--all", action="store_true",
                        help="Run every built-in profile (filterable with --source-kinds).")
    p_prep.add_argument("--source-kinds",
                        help="Comma-separated source kinds to include "
                             "with --all (e.g. 'openml,sklearn' for the UCI subset).")
    p_prep.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT),
                        help=f"Where to write outputs (default: {DEFAULT_OUTPUT_ROOT}).")
    p_prep.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT),
                        help=f"Root for relative source `cached_at` paths "
                             f"(default: {DEFAULT_DATA_ROOT}).")
    p_prep.set_defaults(func=cmd_prepare)

    p_ver = sub.add_parser("verify", help="Verify a previous prepare run "
                                          "against expected_hashes.")
    p_ver.add_argument("--profile", help="Path to a profile YAML.")
    p_ver.add_argument("--all", action="store_true",
                       help="Verify every built-in profile (filterable with --source-kinds).")
    p_ver.add_argument("--source-kinds",
                       help="Comma-separated source kinds to include with --all.")
    p_ver.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p_ver.set_defaults(func=cmd_verify)

    p_dl = sub.add_parser(
        "download",
        help="Fetch + extract a profile's raw data via its source.download_url.",
    )
    p_dl.add_argument("--profile", required=True)
    p_dl.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    p_dl.add_argument("--force", action="store_true",
                      help="Re-download even if cached_at already has data.")
    p_dl.set_defaults(func=cmd_download)

    p_init = sub.add_parser("init-profile", help="Scaffold a profile YAML "
                                                 "from a sample (planned for v0.5).")
    p_init.add_argument("name")
    p_init.add_argument("--source", required=False)
    p_init.add_argument("--source-url", required=False)
    p_init.set_defaults(func=cmd_init_profile)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
