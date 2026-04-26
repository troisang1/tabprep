"""Tests for `tabprep.core.memguard`."""
from __future__ import annotations

import pytest

from tabprep.core.memguard import (
    MemoryGuard,
    RAMBudgetExceeded,
    current_rss_bytes,
    default_budget_bytes,
    resolve_budget_bytes,
    total_ram_bytes,
)


def test_current_rss_bytes_is_positive():
    rss = current_rss_bytes()
    assert isinstance(rss, int)
    assert rss > 0
    # Sanity bound: pytest itself uses tens of MB, less than 16 GiB.
    assert rss < 16 * 1024**3


def test_total_ram_bytes_or_none():
    total = total_ram_bytes()
    assert total is None or (isinstance(total, int) and total > 0)


def test_default_budget_bytes_is_positive():
    assert default_budget_bytes() > 0
    assert default_budget_bytes(0.5) > 0
    # 100% > 80%
    assert default_budget_bytes(1.0) >= default_budget_bytes(0.5)


def test_resolve_budget_bytes_explicit():
    assert resolve_budget_bytes(4) == 4 * 1024**3
    assert resolve_budget_bytes(0.5) == int(0.5 * 1024**3)


def test_resolve_budget_bytes_none_uses_default():
    assert resolve_budget_bytes(None) == default_budget_bytes()


def test_resolve_budget_bytes_rejects_nonpositive():
    with pytest.raises(ValueError):
        resolve_budget_bytes(0)
    with pytest.raises(ValueError):
        resolve_budget_bytes(-1)


def test_memory_guard_check_under_budget_is_noop():
    # Budget far above any reasonable RSS — should not raise.
    g = MemoryGuard(budget_bytes=1024 * 1024**3, label="test")  # 1 TiB
    g.check()  # noop


def test_memory_guard_check_over_budget_raises():
    # Budget of 1 byte — we definitely have more than 1 byte of RSS.
    g = MemoryGuard(budget_bytes=1, label="test")
    with pytest.raises(RAMBudgetExceeded) as excinfo:
        g.check(detail="after some file")
    msg = str(excinfo.value)
    assert "test" in msg
    assert "max_rows_per_file" in msg
    assert "memory_budget_gb" in msg
    assert "after some file" in msg


def test_ram_budget_exceeded_subclasses_memory_error():
    assert issubclass(RAMBudgetExceeded, MemoryError)


def test_memory_guard_default_budget():
    # Without an explicit budget, falls back to default_budget_bytes().
    g = MemoryGuard(label="test")
    assert g.budget_bytes == default_budget_bytes()
