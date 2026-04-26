"""`BaseLoader` — abstract base + utility machinery for dataset loaders.

Every dataset's loader (e.g. `datasets/iot23/loader.py`) subclasses this
and overrides `load(...)` to return a raw `(dataframe, label_column)`
tuple. The class methods on `BaseLoader` provide common operations that
multiple datasets need:

  * Recursive, case-insensitive file discovery.
  * Encoding-tolerant CSV read with utf-8 → latin-1 → cp1252 fallback.
  * Large-file streaming (chunked read).
  * Per-file deterministic head-N sampling (used by datasets like
    IoT-23 whose individual captures dwarf RAM).
  * Stratified fraction sampling that **preserves class distribution**.
    For each class the loader takes `floor(fraction * n_class)` rows
    with a floor of 1 — so a class with even a single row is never
    dropped. The result is a representative subsample of the original
    distribution at any fraction in (0, 1].
  * Per-class cap (subsample to at most N rows per label).

The methods are static so loaders can call them either on the class
directly or via `self.read_csv_with_encoding_fallback(...)`. Every
randomized helper accepts an explicit `seed:int` so the entire dataset
preparation remains reproducible.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd


class BaseLoader(ABC):
    """Abstract base for dataset loaders.

    Subclass and override `load`:

        from tabprep.datasets._base import BaseLoader, loader

        @loader("iot23")
        class IoT23Loader(BaseLoader):
            def load(self, raw_dir, label_col, **opts):
                files = self.recursive_glob(raw_dir, ("*.labeled",))
                ...
                return df, label_col
    """

    # ---------------------------------------------------------------- API

    @abstractmethod
    def load(self, raw_dir: Path, label_col: str,
             **opts: Any) -> tuple[pd.DataFrame, str]:
        """Read the raw bytes under `raw_dir` and return `(df, label_col)`.

        `opts` are forwarded from the profile's `loader_options:` block.
        """
        ...

    # ---------------------------------------------------------- file discovery

    @staticmethod
    def recursive_glob(base: Path,
                       patterns: tuple[str, ...]) -> list[Path]:
        """Recursive, case-insensitive, sorted file discovery.

        Walks `base` and returns every file whose extension (or whole
        name) matches any glob in `patterns`, sorted by full path so
        the read order is deterministic across OSes (HFS+, APFS, ext4
        differ on case-folded glob).

        Each pattern can be a suffix glob (`"*.csv"`) or a basename
        glob (`"conn.log.labeled"`) — handled identically.
        """
        base = Path(base)
        if not base.is_dir():
            raise FileNotFoundError(f"BaseLoader.recursive_glob: not a directory: {base}")
        seen: set[Path] = set()
        results: list[Path] = []
        for pat in patterns:
            for p in base.rglob(pat):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    results.append(p)
            # Case-insensitive variant: try uppercase+lowercase
            # combinations of the suffix.
            if pat.startswith("*.") and any(c.isalpha() for c in pat):
                for variant in {pat.upper(), pat.lower(),
                                pat[:2] + pat[2].upper() + pat[3:].lower()}:
                    if variant == pat:
                        continue
                    for p in base.rglob(variant):
                        if p.is_file() and p not in seen:
                            seen.add(p)
                            results.append(p)
        return sorted(results)

    # ------------------------------------------------------------- CSV reads

    DEFAULT_ENCODINGS = ("utf-8", "latin-1", "cp1252")

    @staticmethod
    def read_csv_with_encoding_fallback(
        path: Path,
        *,
        encodings: tuple[str, ...] | None = None,
        **read_csv_kwargs: Any,
    ) -> pd.DataFrame:
        """Try each encoding in order; return the first DataFrame that decodes.

        - `encodings=None` ⇒ use `BaseLoader.DEFAULT_ENCODINGS`.
        - All other kwargs forwarded verbatim to `pd.read_csv`.
        - Raises if no encoding succeeds.
        """
        encs = encodings or BaseLoader.DEFAULT_ENCODINGS
        last_exc: Exception | None = None
        kwargs = {"low_memory": False, **read_csv_kwargs}
        for enc in encs:
            try:
                return pd.read_csv(path, encoding=enc, **kwargs)
            except UnicodeDecodeError as exc:
                last_exc = exc
                continue
        raise RuntimeError(
            f"BaseLoader.read_csv_with_encoding_fallback: could not decode "
            f"{path} with encodings={encs}: {last_exc}"
        )

    @staticmethod
    def chunked_csv_iter(path: Path, *,
                         chunksize: int = 100_000,
                         **read_csv_kwargs: Any) -> Iterator[pd.DataFrame]:
        """Stream a CSV in chunks of `chunksize` rows. Useful for files that
        don't fit in RAM. Each yielded DataFrame is independent — the
        caller may concat, sample, or write per-chunk.
        """
        kwargs = {"low_memory": False, **read_csv_kwargs}
        for chunk in pd.read_csv(path, chunksize=int(chunksize), **kwargs):
            yield chunk

    @staticmethod
    def read_head_n(path: Path, *, n: int,
                    encodings: tuple[str, ...] | None = None,
                    **read_csv_kwargs: Any) -> pd.DataFrame:
        """Read the first `n` rows of a CSV. Deterministic per-file cap.

        Used by datasets like IoT-23 whose individual capture logs can
        exceed RAM — the per-file head-N strategy bounds memory before
        any concat. The result is biased toward the start of the file
        (intentional: produces reproducible bytes; randomization would
        compromise hash stability without an explicit seed strategy).
        """
        return BaseLoader.read_csv_with_encoding_fallback(
            path,
            encodings=encodings,
            nrows=int(n),
            **read_csv_kwargs,
        )

    @staticmethod
    def read_csv_with_row_cap(
        path: Path,
        *,
        max_rows: int,
        mode: str = "head",
        seed: int = 42,
        chunksize: int = 100_000,
        encodings: tuple[str, ...] | None = None,
        label_column: str | None = None,
        **read_csv_kwargs: Any,
    ) -> pd.DataFrame:
        """Read a CSV with a hard row cap — bounds memory for huge files.

        The CIC-DDoS-2019 dataset ships individual CSVs of multi-GB
        size; reading any of them whole defeats the post-load
        `stratified_fraction_sample` step (we'd OOM before getting
        there). This helper lets the loader stream-read with a
        deterministic bound on the in-memory row count.

        Parameters
        ----------
        max_rows
            Hard cap on the rows returned for this file.
        mode
            - ``"head"``: take the first `max_rows` (cheapest; reads
              only what's needed; biased toward start of file).
              Safe **only** when each file is class-pure (e.g. one
              attack family per CSV) — for class-mixed files head
              risks dropping minorities clustered later in the file.
            - ``"reservoir"``: chunked Algorithm-R reservoir sampling.
              Each row has uniform `max_rows / total_rows` probability.
              Minority classes are sampled proportionally — fine in
              expectation, but a class with very few rows can be
              missed entirely by chance.
            - ``"stratified_by_label"``: two-pass class-aware sample.
              Pass 1 streams only the `label_column` to bin row
              indices by class. Each class then gets
              `max(1, floor(max_rows × n_class / N))` rows sampled
              uniformly from its bucket. Pass 2 streams the file
              again and keeps only the sampled rows. Guarantees
              every class with ≥1 row survives — at the cost of a
              second pass through the file.
        seed
            Deterministic seed for reservoir / stratified modes.
        chunksize
            Streaming chunk size for reservoir / stratified modes.
        encodings, **read_csv_kwargs
            Forwarded to the underlying read.
        label_column
            Required when `mode="stratified_by_label"` — the column
            name in the CSV's header that holds the class label.
            For headerless CSVs (where the loader injects `names=`),
            this must match a name in the injected list.

        Returns
        -------
        pd.DataFrame
            At most `max_rows` rows.
        """
        if max_rows <= 0:
            raise ValueError(f"max_rows must be positive (got {max_rows})")
        if mode == "head":
            return BaseLoader.read_head_n(
                path, n=max_rows, encodings=encodings, **read_csv_kwargs
            )
        if mode == "reservoir":
            return BaseLoader._reservoir_sample_csv(
                path,
                max_rows=int(max_rows),
                seed=int(seed),
                chunksize=int(chunksize),
                encodings=encodings,
                **read_csv_kwargs,
            )
        if mode == "stratified_by_label":
            if not label_column:
                raise ValueError(
                    "stratified_by_label mode requires `label_column`"
                )
            return BaseLoader._stratified_by_label_sample_csv(
                path,
                max_rows=int(max_rows),
                label_column=str(label_column),
                seed=int(seed),
                chunksize=int(chunksize),
                encodings=encodings,
                **read_csv_kwargs,
            )
        raise ValueError(
            f"unknown mode {mode!r} (expected 'head', 'reservoir', "
            f"or 'stratified_by_label')"
        )

    @staticmethod
    def _reservoir_sample_csv(
        path: Path,
        *,
        max_rows: int,
        seed: int,
        chunksize: int,
        encodings: tuple[str, ...] | None,
        **read_csv_kwargs: Any,
    ) -> pd.DataFrame:
        """Stream-read a CSV and reservoir-sample `max_rows` rows.

        Implements algorithm R (Vitter 1985): stream the file in
        chunks, hold a fixed `max_rows`-row reservoir, and replace
        rows with shrinking probability as the input grows. Memory is
        bounded at `max_rows + chunksize` rows regardless of input
        size — this is how a 10 GB CSV fits inside a 1 GB sample.

        Encoding fallback works the same as `read_csv_with_encoding_fallback`
        (try utf-8 → latin-1 → cp1252 unless caller pinned).
        """
        encs = encodings or BaseLoader.DEFAULT_ENCODINGS
        kwargs = {"low_memory": False, **read_csv_kwargs}
        last_exc: Exception | None = None

        for enc in encs:
            try:
                rng = np.random.default_rng(int(seed))
                reservoir: pd.DataFrame | None = None
                seen = 0
                iterator = pd.read_csv(
                    path, encoding=enc, chunksize=int(chunksize), **kwargs
                )
                for chunk in iterator:
                    n = len(chunk)
                    if n == 0:
                        continue
                    if reservoir is None:
                        # Fast path: first chunk → take the head of it
                        # to seed the reservoir.
                        if n <= max_rows:
                            reservoir = chunk.copy()
                            seen = n
                            continue
                        idx = rng.choice(n, size=max_rows, replace=False)
                        reservoir = chunk.iloc[np.sort(idx)].reset_index(drop=True)
                        seen = n
                        continue
                    if len(reservoir) < max_rows:
                        # Reservoir not yet full — pull rows from this
                        # chunk until it is, then switch to replacement.
                        need = max_rows - len(reservoir)
                        if n <= need:
                            reservoir = pd.concat(
                                [reservoir, chunk], ignore_index=True
                            )
                            seen += n
                            continue
                        head = chunk.iloc[:need]
                        reservoir = pd.concat(
                            [reservoir, head], ignore_index=True
                        )
                        seen += need
                        chunk = chunk.iloc[need:].reset_index(drop=True)
                        n = len(chunk)
                    # Algorithm R: each row in `chunk` has probability
                    # max_rows / (seen + i + 1) of replacing a random
                    # reservoir slot. Vectorised: draw uniform indices
                    # in [0, seen+i+1) and accept the ones < max_rows.
                    positions = np.arange(seen + 1, seen + n + 1)
                    j = rng.integers(low=0, high=positions, size=n)
                    accept = j < max_rows
                    if accept.any():
                        slots = j[accept]
                        replacement_rows = chunk.iloc[np.where(accept)[0]]
                        # Replace into the reservoir at `slots`.
                        reservoir.iloc[slots] = replacement_rows.values
                    seen += n

                if reservoir is None:
                    return pd.DataFrame()
                # Final shuffle so the row order does not leak the
                # streaming insertion order.
                idx = rng.permutation(len(reservoir))
                return reservoir.iloc[idx].reset_index(drop=True)
            except UnicodeDecodeError as exc:
                last_exc = exc
                continue
        raise RuntimeError(
            f"BaseLoader._reservoir_sample_csv: could not decode {path} "
            f"with encodings={encs}: {last_exc}"
        )

    @staticmethod
    def _stratified_by_label_sample_csv(
        path: Path,
        *,
        max_rows: int,
        label_column: str,
        seed: int,
        chunksize: int,
        encodings: tuple[str, ...] | None,
        **read_csv_kwargs: Any,
    ) -> pd.DataFrame:
        """Two-pass class-aware row cap — every class with ≥1 row survives.

        Pass 1: stream the file in chunks reading **only** `label_column`.
                Build a dict {label → list of row indices}. Cheap because
                pandas reads single columns ~O(file_bytes / n_cols).

        Plan:   each class C gets
                  k_C = max(1, floor(max_rows × |C| / N))
                rows sampled uniformly from its bucket. The overall total
                may slightly under-shoot `max_rows` because of the floor=1
                rule on tiny classes; this is intentional — the contract
                is "no class is silently dropped".

        Pass 2: stream the file again, keep only rows whose absolute
                index appears in the sampled set, accumulate, return.

        Memory bound:  O(N × sizeof(label_dtype)) for pass 1's index
        bookkeeping + O(max_rows × n_cols) for pass 2's accumulator —
        both far smaller than the full uncapped read.

        For headerless CSVs the caller must supply `header` and `names`
        in `read_csv_kwargs`; pass 1 will then load only the named
        `label_column` from the injected schema. (Pandas accepts
        `usecols=[label_column]` in combination with `names=…` as long
        as the requested name is in the names list.)
        """
        encs = encodings or BaseLoader.DEFAULT_ENCODINGS
        kwargs = {"low_memory": False, **read_csv_kwargs}
        last_exc: Exception | None = None

        for enc in encs:
            try:
                # ---- Pass 1: read only the label column to bin row indices.
                pass1_kwargs = dict(kwargs)
                pass1_kwargs["usecols"] = [label_column]
                buckets: dict[Any, list[int]] = {}
                row_idx = 0
                for chunk in pd.read_csv(
                    path, encoding=enc,
                    chunksize=int(chunksize),
                    **pass1_kwargs,
                ):
                    if label_column not in chunk.columns:
                        raise KeyError(
                            f"stratified_by_label: column {label_column!r} "
                            f"not found (got {list(chunk.columns)})"
                        )
                    labels = chunk[label_column].tolist()
                    for j, lab in enumerate(labels):
                        # Treat NaN-as-string consistently — float('nan')
                        # is unequal to itself which would split the
                        # NaN-class across many buckets. Use the repr.
                        if isinstance(lab, float) and lab != lab:           # NaN check
                            key = "__NAN__"
                        else:
                            key = lab
                        buckets.setdefault(key, []).append(row_idx + j)
                    row_idx += len(chunk)

                total = sum(len(v) for v in buckets.values())
                if total == 0:
                    return pd.DataFrame()

                # If the file has fewer rows than the cap, we'd just
                # take everything — no need for pass 2 with a row filter.
                if total <= max_rows:
                    return BaseLoader.read_csv_with_encoding_fallback(
                        path, encodings=(enc,), **read_csv_kwargs
                    )

                # ---- Plan: per-class sample sizes + sampled index set.
                rng = np.random.default_rng(int(seed))
                wanted: set[int] = set()
                for key, idxs in buckets.items():
                    n_class = len(idxs)
                    k = max(1, int(math.floor(max_rows * n_class / total)))
                    if k >= n_class:
                        wanted.update(idxs)
                    else:
                        chosen = rng.choice(np.asarray(idxs), size=k, replace=False)
                        wanted.update(int(x) for x in chosen)

                # ---- Pass 2: stream again, filter on absolute row index.
                parts: list[pd.DataFrame] = []
                row_idx = 0
                for chunk in pd.read_csv(
                    path, encoding=enc,
                    chunksize=int(chunksize),
                    **kwargs,
                ):
                    n = len(chunk)
                    chunk_indices = range(row_idx, row_idx + n)
                    keep_local = [i - row_idx for i in chunk_indices if i in wanted]
                    if keep_local:
                        parts.append(chunk.iloc[keep_local].copy())
                    row_idx += n

                if not parts:
                    return pd.DataFrame()
                out = pd.concat(parts, ignore_index=True)
                # Final shuffle so per-class block ordering doesn't leak.
                idx = rng.permutation(len(out))
                return out.iloc[idx].reset_index(drop=True)
            except UnicodeDecodeError as exc:
                last_exc = exc
                continue
        raise RuntimeError(
            f"BaseLoader._stratified_by_label_sample_csv: could not decode "
            f"{path} with encodings={encs}: {last_exc}"
        )

    # ----------------------------------------------------- stratified sampling

    @staticmethod
    def stratified_fraction_sample(
        df: pd.DataFrame,
        *,
        label_col: str,
        fraction: float,
        seed: int,
    ) -> pd.DataFrame:
        """Take `fraction` of total rows, **stratified per class**.

        For each class:
          1. shuffle deterministically by `seed`,
          2. take `max(1, floor(fraction * n_class))` rows.

        The resulting subsample preserves the original class proportions
        to within rounding (option-b semantics — never drops a class
        with at least one sample). The whole result is then shuffled
        once more by `seed` so the row order doesn't reveal the
        per-class block structure.

        - `fraction` must be in (0, 1]. If `fraction == 1.0` you get the
          original distribution (just deterministically shuffled).
        - Raises if `label_col` is missing.
        """
        if not 0 < fraction <= 1:
            raise ValueError(f"fraction must be in (0, 1] (got {fraction})")
        if label_col not in df.columns:
            raise KeyError(f"label_col {label_col!r} not in dataframe")

        parts: list[pd.DataFrame] = []
        for label, group in df.groupby(label_col, sort=True):
            n = len(group)
            if n == 0:
                continue
            k = max(1, int(math.floor(n * float(fraction))))
            shuffled = group.sample(frac=1.0, random_state=int(seed)).reset_index(drop=True)
            parts.append(shuffled.iloc[:k])

        if not parts:
            return df.iloc[0:0].copy()

        out = pd.concat(parts, ignore_index=True)
        return out.sample(frac=1.0, random_state=int(seed)).reset_index(drop=True)

    @staticmethod
    def cap_per_class(df: pd.DataFrame, *,
                      label_col: str,
                      cap: int,
                      seed: int) -> pd.DataFrame:
        """Subsample each class to at most `cap` rows.

        Deterministic by `seed`. Classes with fewer than `cap` rows are
        kept whole. Used for class-balanced grids where the tail
        classes are intentionally oversampled.
        """
        if label_col not in df.columns:
            raise KeyError(f"label_col {label_col!r} not in dataframe")
        return (
            df.groupby(label_col, group_keys=False, sort=True)
              .apply(lambda x: x.sample(n=min(len(x), int(cap)),
                                        random_state=int(seed)))
              .reset_index(drop=True)
        )
