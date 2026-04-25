"""HTTP fetch + archive extract for the auto-download path.

A profile may declare a `source.download_url` pointing at a single file
(plain CSV, single Zeek log) or an archive (tarball / tar.gz / tgz /
zip). When `tabprep prepare` runs and the local `cached_at` directory
is empty, this module fetches the URL, verifies SHA-256 if pinned,
unpacks if necessary, and leaves the data in place. Subsequent runs
detect the populated directory and skip download.

Stays at this layer (no third-party deps beyond `requests`, which is
already in the package's dependency list) — no progress-bar libraries,
no async, no resumable downloads. Simple, deterministic, debuggable.
"""
from __future__ import annotations

import hashlib
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable

import requests

CHUNK = 1 << 20                                  # 1 MiB streaming chunks
PROGRESS_EVERY_BYTES = 64 * (1 << 20)            # log every 64 MiB


_SUPPORTED_FORMATS = ("tar.gz", "tgz", "tar", "zip", "gz", "none")


def detect_archive_format(url: str, override: str | None = None) -> str:
    """Return the archive format tag based on the URL's suffix.

    Override is used when the URL doesn't carry a recognisable extension
    (e.g. some download services embed a content-disposition).
    """
    if override:
        if override not in _SUPPORTED_FORMATS:
            raise ValueError(f"unsupported archive_format {override!r}; "
                             f"supported: {_SUPPORTED_FORMATS}")
        return override
    lower = url.lower().rsplit("?", 1)[0]        # strip querystring
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar.gz"
    if lower.endswith(".tar"):
        return "tar"
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith(".gz"):
        return "gz"
    return "none"                                # treat as raw single file


def _has_data(path: Path) -> bool:
    """Idempotency check: is `path` populated with any non-empty file?"""
    if not path.exists():
        return False
    if path.is_file():
        return path.stat().st_size > 0
    if path.is_dir():
        for p in path.rglob("*"):
            if p.is_file() and p.stat().st_size > 0:
                return True
    return False


def derive_target_name(url: str) -> str:
    """Best-effort guess at what filename a URL should write to locally.

    Walks the URL **path** (host and querystring excluded) right-to-left
    and returns the first segment with a file extension. Handles
    Zenodo-style URLs where the last path segment is the literal word
    `content` or `download`. If no path segment has a file extension,
    falls back to the last path segment, then to `'downloaded.bin'`
    when the path itself is empty.

    Earlier versions naively `.split("/")` the whole URL, which let the
    dotted hostname (`example.com`) match the "first segment with a `.`"
    rule before any path segment was inspected — so a URL with no
    extension in its path returned the host. Fixed by using
    `urllib.parse.urlparse` to scope the search to `.path`.
    """
    from urllib.parse import urlparse
    parts = [p for p in urlparse(url).path.split("/") if p]
    for part in reversed(parts):
        if "." in part:
            return part
    return parts[-1] if parts else "downloaded.bin"


def _stream_download(url: str, dest: Path) -> str:
    """Download `url` to `dest` (file path). Returns the SHA-256 hex of
    the bytes written. Streams in chunks to keep memory bounded; logs
    progress every 64 MiB.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    n = 0
    next_log = PROGRESS_EVERY_BYTES
    print(f"[tabprep] fetching {url}")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", "0") or 0)
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=CHUNK):
                if not chunk:
                    continue
                fh.write(chunk)
                h.update(chunk)
                n += len(chunk)
                if n >= next_log:
                    if total:
                        pct = (n / total) * 100
                        print(f"          {n // (1 << 20)} MiB / "
                              f"{total // (1 << 20)} MiB ({pct:.0f}%)")
                    else:
                        print(f"          {n // (1 << 20)} MiB")
                    next_log += PROGRESS_EVERY_BYTES
    print(f"[tabprep] downloaded {n // (1 << 20)} MiB to {dest}")
    return h.hexdigest()


def _verify_sha256(observed: str, expected: str | None, label: str) -> None:
    if not expected:
        return
    if observed != expected:
        raise RuntimeError(
            f"{label}: SHA-256 mismatch\n"
            f"  expected: {expected}\n"
            f"  observed: {observed}\n"
            f"  the upstream file may have changed; re-pin the profile."
        )


def _extract_tar(src: Path, dest_dir: Path, gz: bool = False) -> None:
    mode = "r:gz" if gz else "r"
    print(f"[tabprep] extracting tar{'.gz' if gz else ''} → {dest_dir}")
    with tarfile.open(src, mode) as tf:
        # Path-traversal guard: refuse any member whose resolved path
        # escapes dest_dir (Python <3.12 lets `../` slip through tar).
        safe_dir = dest_dir.resolve()
        for m in tf.getmembers():
            target = (safe_dir / m.name).resolve()
            if not str(target).startswith(str(safe_dir)):
                raise RuntimeError(f"refusing unsafe tar member: {m.name}")
        tf.extractall(dest_dir)


def _extract_zip(src: Path, dest_dir: Path) -> None:
    print(f"[tabprep] extracting zip → {dest_dir}")
    safe_dir = dest_dir.resolve()
    with zipfile.ZipFile(src) as zf:
        for n in zf.namelist():
            target = (safe_dir / n).resolve()
            if not str(target).startswith(str(safe_dir)):
                raise RuntimeError(f"refusing unsafe zip member: {n}")
        zf.extractall(dest_dir)


def _extract_gz(src: Path, dest_dir: Path) -> None:
    """Single-stream gzip — produces one decompressed file under dest_dir."""
    import gzip
    print(f"[tabprep] decompressing gz → {dest_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / src.with_suffix("").name
    with gzip.open(src, "rb") as gh, out.open("wb") as fh:
        shutil.copyfileobj(gh, fh)


def download_and_extract(
    url: str,
    cached_at: Path,
    *,
    archive_format: str | None = None,
    expected_sha256: str | None = None,
    target_name: str | None = None,
    force: bool = False,
) -> None:
    """Idempotent download + extract.

    Idempotency model:
      - If `target_name` is provided, the cache is considered populated
        when `cached_at / target_name` already exists with size > 0.
        Used by multi-URL profiles so each URL has independent
        existence-tracking.
      - If `target_name` is None, the cache is populated when
        `cached_at` recursively contains any non-empty file. Used by
        single-URL profiles whose payload is an archive that explodes
        into many sub-paths.

    Behaviour:
      - Downloads `url` to a `_download.part` temp under `cached_at`.
      - Optionally verifies SHA-256 against `expected_sha256`.
      - Extracts by `archive_format` (auto-detected from URL extension
        when unspecified) into `cached_at`.
      - For `archive_format = "none"` the file is renamed into
        `cached_at / target_name` (or `cached_at / <url-basename>` if
        target_name is None).
    """
    cached_at = Path(cached_at)
    cached_at.mkdir(parents=True, exist_ok=True)

    if not force:
        if target_name is not None:
            t = cached_at / target_name
            if t.is_file() and t.stat().st_size > 0:
                print(f"[tabprep] cache hit: {t} already present, skipping download")
                return
        elif _has_data(cached_at):
            print(f"[tabprep] cache hit: {cached_at} already populated, skipping download")
            return

    fmt = detect_archive_format(url, archive_format)

    tmp = cached_at / "_download.part"
    if tmp.exists():
        tmp.unlink()

    observed = _stream_download(url, tmp)
    _verify_sha256(observed, expected_sha256, f"download {url}")

    try:
        if fmt == "tar.gz":
            _extract_tar(tmp, cached_at, gz=True)
        elif fmt == "tar":
            _extract_tar(tmp, cached_at, gz=False)
        elif fmt == "zip":
            _extract_zip(tmp, cached_at)
        elif fmt == "gz":
            _extract_gz(tmp, cached_at)
        elif fmt == "none":
            # Single file. Use explicit target_name if given, else derive
            # from the URL.
            name = target_name or derive_target_name(url)
            tmp.rename(cached_at / name)
            tmp = None                                # rename consumed it
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def discover_downloadable(
    profiles: Iterable[Path]
) -> list[tuple[Path, str]]:
    """Return [(profile_path, download_url)] for every profile carrying
    a `source.download_url`. Helper for `tabprep download --all`.
    """
    out: list[tuple[Path, str]] = []
    from tabprep.core.profile import load_profile
    for p in profiles:
        try:
            prof = load_profile(p)
        except Exception:                                              # noqa: BLE001
            continue
        if prof.source.download_url:
            out.append((p, prof.source.download_url))
    return out
