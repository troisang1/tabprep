"""tabprep CLI — `tabprep prepare|verify|list|init-profile`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tabprep import __version__
from tabprep.core.hashing import canonical_sha256_of_file
from tabprep.core.pipeline import run_pipeline
from tabprep.core.profile import Profile, load_profile

DEFAULT_OUTPUT_ROOT = Path("../processed")          # relative to cnNFST/data/tabprep/
DEFAULT_DATA_ROOT = Path("..")                       # ditto — points at cnNFST/data/
DEFAULT_BUILTIN_DIR = Path(__file__).parent.parent / "profiles" / "builtin"


def _builtin_profiles() -> list[Path]:
    if not DEFAULT_BUILTIN_DIR.is_dir():
        return []
    return sorted(DEFAULT_BUILTIN_DIR.glob("*.yaml"))


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


def _prepare_one(profile: Profile, out_root: Path, data_root: Path) -> int:
    if profile.source.cached_at:
        cached = Path(profile.source.cached_at)
        if not cached.is_absolute():
            profile.source.cached_at = str((data_root / cached).resolve())
    print(f"[tabprep] prepare {profile.name} v{profile.version}")
    print(f"          source: kind={profile.source.kind} name={profile.source.name}")
    if profile.source.cached_at:
        print(f"          cached_at: {profile.source.cached_at}")
    print(f"          output: {out_root.resolve() / profile.name}")
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


def cmd_init_profile(args: argparse.Namespace) -> int:
    """Stub — full implementation slated for v0.5."""
    print("[tabprep] init-profile is not yet implemented.\n"
          "  See README.md ('Authoring a custom profile') for the planned UX.\n"
          "  For now, copy profiles/builtin/pendigits.yaml as a starting point\n"
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
