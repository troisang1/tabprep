"""tabprep CLI — `tabprep prepare|verify|list|init-profile`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tabprep import __version__
from tabprep.core.hashing import canonical_sha256_of_file
from tabprep.core.pipeline import run_pipeline
from tabprep.core.profile import load_profile

DEFAULT_OUTPUT_ROOT = Path("../processed")          # relative to cnNFST/data/tabprep/
DEFAULT_DATA_ROOT = Path("..")                       # ditto — points at cnNFST/data/
DEFAULT_BUILTIN_DIR = Path(__file__).parent.parent / "profiles" / "builtin"


def _builtin_profiles() -> list[Path]:
    if not DEFAULT_BUILTIN_DIR.is_dir():
        return []
    return sorted(DEFAULT_BUILTIN_DIR.glob("*.yaml"))


def cmd_list(args: argparse.Namespace) -> int:
    profiles = _builtin_profiles()
    if not profiles:
        print("(no built-in profiles found)")
        return 0
    print(f"Built-in profiles ({len(profiles)}):")
    for p in profiles:
        try:
            prof = load_profile(p)
            print(f"  {prof.name:<20} v{prof.version}   {prof.description}")
        except Exception as exc:                                      # noqa: BLE001
            print(f"  {p.name}: <invalid: {exc}>")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    out_root = Path(args.output_root).expanduser()
    data_root = Path(args.data_root).expanduser()
    # Resolve relative cached_at paths against --data-root.
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

    # Optional: cross-check against `expected_hashes` if the profile carries them.
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


def cmd_verify(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    if not profile.expected_hashes:
        print(f"[skip] {profile.name}: no expected_hashes in profile.")
        return 0
    out_dir = Path(args.output_root).expanduser() / profile.name
    if not out_dir.is_dir():
        print(f"[FAIL] no output dir at {out_dir} — run `tabprep prepare` first.",
              file=sys.stderr)
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


def cmd_init_profile(args: argparse.Namespace) -> int:
    """Stub for v0.2 — not implemented yet."""
    print("[tabprep] init-profile is not yet implemented in v0.1.\n"
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
    p_prep.add_argument("--profile", required=True, help="Path to a profile YAML.")
    p_prep.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT),
                        help=f"Where to write outputs (default: {DEFAULT_OUTPUT_ROOT}).")
    p_prep.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT),
                        help=f"Root for relative source `cached_at` paths "
                             f"(default: {DEFAULT_DATA_ROOT}).")
    p_prep.set_defaults(func=cmd_prepare)

    p_ver = sub.add_parser("verify", help="Verify a previous prepare run "
                                          "against expected_hashes.")
    p_ver.add_argument("--profile", required=True)
    p_ver.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    p_ver.set_defaults(func=cmd_verify)

    p_init = sub.add_parser("init-profile", help="Scaffold a profile YAML "
                                                 "from a sample (v0.2 todo).")
    p_init.add_argument("name")
    p_init.add_argument("--source", required=False)
    p_init.add_argument("--source-url", required=False)
    p_init.set_defaults(func=cmd_init_profile)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
