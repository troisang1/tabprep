# tabprep design

Quick reference. The intended audience is contributors and integrators.

## Layered architecture

```
                         ┌────────────────────────┐
                         │ profile YAML           │
                         │  source / pipeline /   │
                         │  split / output / hash │
                         └────────────┬───────────┘
                                      │
                                      ▼
                       ┌────────────────────────────┐
        load_profile → │ Profile (dataclass)        │
                       └──────────────┬─────────────┘
                                      │
                                      ▼
              ┌──────────────┬────────────────┬───────────────┐
              │ source       │ pipeline ops   │ split         │
              │ registry     │ registry       │ registry      │
              └──────┬───────┴────────┬───────┴──────┬────────┘
                     │                │              │
                     ▼                ▼              ▼
                 load raw         apply ops    train/cal/test
                 (df, label_col)  (df → df)    (3 dataframes)
                                                     │
                                                     ▼
                                            canonical CSV writer
                                                     │
                                                     ▼
                                           manifest.json + sha256
```

## Determinism contract

For a given profile and a given source-bytes input:

1. `np.random.default_rng(seed)` for any randomized op (subsample, shuffle).
2. `pandas.groupby(..., sort=True)` everywhere — never rely on insertion order.
3. `set(...)` is forbidden in deterministic paths; use `sorted(...)`.
4. `pd.get_dummies` is fed `sorted(columns)` so encoded-column order is stable.
5. The canonical CSV writer:
   * sorts columns alphabetically (or `source_order` if explicitly opted in);
   * sorts rows by per-row sha256, then permutes by `row_shuffle_seed`;
   * formats floats with `f"{x:.{precision}f}"` (no platform `%g`);
   * uses `\n` line terminator; no platform `\r\n`;
   * RFC4180-style minimal quoting (only when comma/newline/quote present).
6. Source integrity is checked via SHA-256 over the raw download (when
   `source.sha256` is set in the profile). If the upstream changes, the
   pipeline aborts with a clear diff message rather than silently producing
   different outputs.

## Adding a new op

```python
# tabprep/ops/your_op.py
import pandas as pd
from tabprep.ops._registry import op

@op("my_drop_zeros")
def my_drop_zeros(df: pd.DataFrame, *, label_col: str,
                  columns: list[str]) -> pd.DataFrame:
    keep = ~(df[columns].sum(axis=1) == 0)
    return df[keep].reset_index(drop=True)
```

Then `import tabprep.ops.your_op` in `tabprep/ops/__init__.py` so the
registry sees it at package import time.

The op signature is fixed: it always receives `df: pd.DataFrame` and the
keyword `label_col: str`, plus any params declared in the profile YAML.
Return a new dataframe — never mutate in place.

## Adding a new source kind

```python
# tabprep/sources/my_source.py
import pandas as pd
from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

@source("my_kind")
def load_my(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    df = ...
    return df, label
```

## Adding a new dataset profile

For built-in datasets, the cleanest path is:

1. Find an OpenML/sklearn loader if one exists — that is the cheapest source.
2. Otherwise, document the manual download path under `data/raw/<name>/`,
   record the SHA-256, set `source.kind = url` with `cached_at` and `sha256`.
3. Run `python -m tabprep prepare --profile profiles/builtin/<name>.yaml`.
4. Copy the printed SHA-256 values into the profile's `expected_hashes`.
5. Re-run `prepare`; verify it reports `expected_hashes match — fully reproduced.`
6. Commit.

For user datasets that we don't ship a profile for, future versions will
provide `tabprep init-profile <name> --source <path>` that scaffolds the
YAML with sensible defaults inferred from the schema. v0.1 ships a stub
that points users at the README.
