"""Lightweight RAM watchdog for dataset loaders.

The CSV-concatenating loaders (`concat_csvs`, `cic_apt_iiot`, `insdn`,
`iot23`) read every file into a list of DataFrames before `pd.concat`.
On the heavy IDS datasets (CIC-DDoS-2019 = 29 GB raw, CIC-IDS-2018 =
6.5 GB raw, CIC-APT-IIoT-2024 = 9.2 GB raw) this can exhaust RAM and
push the process into swap, where the kernel either OOM-kills it or
the host grinds to a halt. This module is the brake.

Two pieces:

  * `current_rss_bytes()` — best-effort RSS measurement using
    `resource.getrusage`. Handles the macOS-vs-Linux unit difference
    (`ru_maxrss` is bytes on Darwin, KiB on Linux/BSD).
  * `MemoryGuard(budget_bytes, label)` — call `.check()` between
    units of work. If RSS exceeds the budget, it raises
    `RAMBudgetExceeded` with an actionable message that points the
    caller at the `max_rows_per_file` / `memory_budget_gb` knobs.

The default budget, when `memory_budget_gb` is unset, is 80% of total
system RAM (best-effort via `os.sysconf` on Unix; falls back to 8 GiB
on platforms where total RAM cannot be queried). Setting an explicit
budget is preferred for reproducibility; the default is a guard rail
so an un-tuned loader cannot bring down the host.
"""
from __future__ import annotations

import os
import platform
import resource
from typing import Optional

# Conversion factors for `ru_maxrss` — Linux/BSD report KiB, Darwin
# reports bytes. (POSIX leaves this implementation-defined, which is
# why every cross-platform memory tool re-derives it.)
_IS_DARWIN = platform.system() == "Darwin"


class RAMBudgetExceeded(MemoryError):
    """Raised by `MemoryGuard.check` when RSS crosses the budget.

    Subclasses `MemoryError` so callers that catch broad memory
    failures still see this as one. The message includes the current
    RSS, the budget, and a hint about the loader knobs that bound it.
    """


def current_rss_bytes() -> int:
    """Return the current process's resident set size in bytes.

    Uses `resource.getrusage(RUSAGE_SELF).ru_maxrss`. Note the unit
    quirk: Linux/BSD report KiB, Darwin reports bytes. We normalise to
    bytes for callers.
    """
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if _IS_DARWIN:
        return int(raw)
    return int(raw) * 1024


def total_ram_bytes() -> Optional[int]:
    """Best-effort total system RAM in bytes, or None if unknown.

    Uses `os.sysconf("SC_PHYS_PAGES") * SC_PAGE_SIZE` on Unix. Returns
    None on platforms (Windows, restricted sandboxes) where the call
    fails — the caller then falls back to a conservative default.
    """
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return int(pages) * int(page_size)
    except (ValueError, OSError, AttributeError):
        pass
    return None


def default_budget_bytes(fraction: float = 0.8) -> int:
    """Default RAM budget = `fraction` of detected total RAM.

    Falls back to 8 GiB if total RAM can't be detected. The 0.8
    fraction leaves headroom for the OS, the kernel page cache, and
    the post-load pipeline ops (one-hot encoding doubles or triples
    the footprint of a wide IDS table).
    """
    total = total_ram_bytes()
    if total is None:
        return 8 * 1024**3
    return int(total * float(fraction))


class MemoryGuard:
    """Bounded-budget RAM watchdog called between units of loader work.

    Usage:

        guard = MemoryGuard(budget_bytes=10 * 1024**3, label="concat_csvs")
        for f in files:
            df = pd.read_csv(f)
            parts.append(df)
            guard.check(detail=f"after reading {f.name}")

    Parameters
    ----------
    budget_bytes
        Hard cap on RSS in bytes. If `None`, uses
        `default_budget_bytes()` (80% of detected total RAM).
    label
        Short identifier embedded in error messages so the user can
        tell which loader hit the cap.

    Notes
    -----
    `ru_maxrss` is the high-water mark, not the instantaneous RSS, so
    once RSS climbs it never reports lower even after a `del`. That is
    fine for our use: we want to abort as soon as the high-water mark
    crosses the budget — DataFrames freed by the user *between* checks
    are still bytes the loader had at some point in time, and counting
    them prevents oscillation near the cliff.
    """

    def __init__(
        self,
        budget_bytes: Optional[int] = None,
        *,
        label: str = "loader",
    ) -> None:
        self.budget_bytes = (
            int(budget_bytes) if budget_bytes is not None else default_budget_bytes()
        )
        self.label = label
        self.start_rss = current_rss_bytes()

    @property
    def current_rss(self) -> int:
        return current_rss_bytes()

    def check(self, *, detail: str = "") -> None:
        """Raise `RAMBudgetExceeded` if RSS has crossed the budget."""
        rss = current_rss_bytes()
        if rss > self.budget_bytes:
            tail = f" ({detail})" if detail else ""
            raise RAMBudgetExceeded(
                f"{self.label}: RSS {_fmt_gb(rss)} exceeded budget "
                f"{_fmt_gb(self.budget_bytes)}{tail}. Reduce memory by "
                f"setting `loader_options.max_rows_per_file` (head-N per "
                f"file) or raise the cap with `loader_options."
                f"memory_budget_gb`. See "
                f"tabprep/core/memguard.py for details."
            )


def _fmt_gb(n: int) -> str:
    """Human-readable GiB string for error messages."""
    return f"{n / 1024**3:.2f} GiB"


def resolve_budget_bytes(memory_budget_gb: Optional[float]) -> int:
    """Translate a profile's `memory_budget_gb` knob into bytes.

    `None` (the default) → 80% of detected total RAM. A positive number
    is interpreted as gibibytes (2**30 bytes) and used verbatim.
    """
    if memory_budget_gb is None:
        return default_budget_bytes()
    if memory_budget_gb <= 0:
        raise ValueError(
            f"memory_budget_gb must be positive (got {memory_budget_gb})"
        )
    return int(float(memory_budget_gb) * 1024**3)
