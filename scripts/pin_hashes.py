"""Read a profile's run manifest and write its file SHA-256s back into the
profile's `expected_hashes` block. Use after the first canonical run of a
new profile to lock in its reproducibility fingerprint.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def pin(profile_path: Path, output_root: Path) -> None:
    with profile_path.open("r", encoding="utf-8") as fh:
        prof_text = fh.read()
    with profile_path.open("r", encoding="utf-8") as fh:
        prof = yaml.safe_load(fh)

    out_dir = output_root / prof["name"]
    manifest_path = out_dir / "_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found at {manifest_path}; "
                                f"run `tabprep prepare` first")
    with manifest_path.open("r", encoding="utf-8") as fh:
        m = json.load(fh)

    new_hashes = {f["path"]: f["sha256"] for f in m["files"]}

    block_lines = ["expected_hashes:"]
    for path in sorted(new_hashes):
        block_lines.append(f"  {path}: {new_hashes[path]}")
    block_text = "\n".join(block_lines) + "\n"

    # Replace existing expected_hashes block if present, else append.
    if "\nexpected_hashes:" in prof_text or prof_text.startswith("expected_hashes:"):
        out_lines: list[str] = []
        in_block = False
        for line in prof_text.splitlines(keepends=True):
            stripped = line.rstrip("\n")
            if stripped == "expected_hashes:" or stripped.startswith("expected_hashes:"):
                in_block = True
                continue
            if in_block:
                # Block ends on the first non-indented, non-empty line.
                if stripped == "" or stripped.startswith(" ") or stripped.startswith("\t") \
                        or stripped.startswith("#"):
                    if stripped == "" or stripped.startswith("#"):
                        # Drop blank/comment lines that were part of the old block.
                        if stripped.startswith("#") and "expected_hashes" in prof_text.split(stripped)[0].rsplit("\n", 2)[-2:]:
                            pass
                    continue
                in_block = False
            out_lines.append(line)
        new_text = "".join(out_lines).rstrip("\n") + "\n\n" + block_text
    else:
        new_text = prof_text.rstrip("\n") + "\n\n" + block_text

    with profile_path.open("w", encoding="utf-8") as fh:
        fh.write(new_text)
    print(f"[ok] {profile_path.name}: pinned {len(new_hashes)} file(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--profile", required=False,
                        help="Path to a single profile YAML (else --all).")
    parser.add_argument("--all", action="store_true",
                        help="Pin every profile under profiles/builtin/.")
    parser.add_argument("--output-root", default="../tabprep_out")
    args = parser.parse_args()

    if not args.profile and not args.all:
        parser.error("specify --profile <yaml> or --all")

    out_root = Path(args.output_root).expanduser()
    if args.all:
        builtin = Path("profiles/builtin")
        for p in sorted(builtin.glob("*.yaml")):
            try:
                pin(p, out_root)
            except FileNotFoundError as exc:
                print(f"[skip] {p.name}: {exc}")
    else:
        pin(Path(args.profile), out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
