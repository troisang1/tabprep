# Contributing to tabprep

Thanks for considering a contribution. tabprep stays small and focused
on one promise — *same profile in, same bytes out, on any machine* — so
the bar for new features is "does it serve the reproducibility
contract?".

This guide is organised easiest → most involved:

- [Setup](#setup)
- [The 90% case: adding a new profile](#adding-a-new-profile)
- [Running tests](#running-tests)
- [Adding a new op](#adding-a-new-op)
- [Adding a new dataset package (v0.5)](#adding-a-new-dataset-package)
- [Code style](#code-style)
- [Commit message style](#commit-message-style)
- [PR checklist](#pr-checklist)
- [What we won't merge](#what-we-wont-merge)

---

## Setup

```bash
git clone https://github.com/troisang1/tabprep.git
cd tabprep
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Python ≥ 3.10. Linux, macOS, and Windows all work; CI runs Linux only.

---

## Adding a new profile

The most common contribution. The fastest path:

1. **Find a working public download URL.** Try:
   - **Kaggle** (`https://www.kaggle.com/api/v1/datasets/download/<owner>/<name>`)
     — most CC-BY datasets serve via GET without auth.
   - **Zenodo** (`https://zenodo.org/api/records/<id>/files/<name>/content`)
     — academic record mirrors, well-versioned.
   - **OpenML / sklearn** — small UCI tabular datasets only.
   - Direct UCI / Stratosphere / lab mirrors — fine if no licence
     form is required.
2. **Copy the closest built-in profile** as a template:

   ```bash
   cp tabprep/profiles/builtin/cicids2018.yaml \
      tabprep/profiles/builtin/my_dataset.yaml
   $EDITOR tabprep/profiles/builtin/my_dataset.yaml
   ```

3. **Adjust the recipe.** What changes for a new dataset:
   - `name`, `version`, `description`
   - `source.download_url` (or `download_urls` for multi-file)
   - `source.archive_format` if zip/tar
   - `label.source_column` — the column holding the class label
   - `label.also_drop` — sibling target columns to remove (see 6)
   - The pipeline ops (drop the right ID columns, encode the right
     categoricals, etc.)
4. **Standardised pipeline tail.** Every profile should end with:

   ```yaml
   - op: filter_min_class_count
     min_count: 50
   - op: stratified_fraction_sample        # 5% benchmark slice
     fraction: 0.05
     seed: 42
   ```

   Standardised across profiles so users get comparable benchmark
   sizes regardless of dataset. Override the fraction if the user
   needs the full set.
5. **Don't apply scaling / normalisation in the pipeline.** Raw
   feature values pass through. The model boundary is where scaling
   belongs.
6. **Remove the three kinds of leakage** (see
   [`docs/adding_a_dataset.md`](docs/adding_a_dataset.md) for the full table):
   - **Sibling labels** → `label.also_drop: [...]`. A dataset often ships
     several mutually-derived targets (binary + multi-class + sub-labels,
     or a per-device identity like N-BaIoT `DeviceName`). Pick one via
     `source_column`; list the rest in `also_drop` — they're labels, not
     features, and run before the pipeline so you can't forget them.
   - **IP / MAC addresses** → `op: drop_ip_columns` (also drops the
     CICFlowMeter `Flow ID`). **Ports are kept on purpose.**
   - **Timestamps** → `op: drop_timestamp_columns` (absolute capture
     time only; elapsed-time / IAT features are kept).
7. **Run + verify:**

   ```bash
   tabprep prepare --profile tabprep/profiles/builtin/my_dataset.yaml
   ```

   Confirm the row counts and class counts make sense. If you want
   the profile to enforce byte-stability, pin the hashes:

   ```bash
   python scripts/pin_hashes.py --profile tabprep/profiles/builtin/my_dataset.yaml
   tabprep verify --profile my_dataset       # must pass
   ```

   Pinning is **optional** — many of the standardised profiles ship
   without `expected_hashes` so they don't false-fail on minor
   pandas-version drift. Pin only when you need a hard contract.
8. **Update the README** — add your dataset to the built-in profile
   table.

For **huge datasets** (multi-GB raw, > host RAM): use
`max_rows_per_file` + `sample_mode: stratified_by_label` in
`loader_options`. See `cic_ddos2019.yaml` for a worked example.

---

## Running tests

```bash
pytest -q                                # smoke tests (no network)
pytest -q --cov=tabprep --cov-report=term  # with coverage

# Reproduce the UCI subset end-to-end (needs network)
tabprep prepare --all --source-kinds openml,sklearn --output-root prepared
tabprep verify  --all --source-kinds openml,sklearn --output-root prepared
```

The IDS profiles need raw data at `raw/<name>/`. The first run
auto-downloads; subsequent runs hit the cache. Don't commit raw data.

---

## Adding a new op

Drop a Python file under `tabprep/ops/` and register the function
with the `@op` decorator:

```python
# tabprep/ops/my_op.py
import pandas as pd
from tabprep.ops._registry import op

@op("my_drop_zeros")
def my_drop_zeros(df: pd.DataFrame, *, label_col: str,
                  columns: list[str]) -> pd.DataFrame:
    """Drop rows whose values across `columns` sum to zero."""
    keep = ~(df[columns].sum(axis=1) == 0)
    return df[keep].reset_index(drop=True)
```

Then add `import tabprep.ops.my_op  # noqa: F401` to
`tabprep/ops/__init__.py` so the registry sees it.

**Op contract:**

- Signature: `fn(df, *, label_col, **params) -> df`. Params are
  keyword-only and match the YAML keys verbatim.
- Pure. Don't mutate `df`; return a new DataFrame.
- Deterministic. If randomized, accept a `seed: int` and use it
  via `random_state=seed` / `np.random.default_rng(seed)`.
- One concept per op. If your docstring has more than 3 paragraphs,
  it's probably two ops.

**Test it.** Add a test under `tests/test_ops.py` that uses
`OP_REGISTRY["my_drop_zeros"](...)`.

---

## Adding a new dataset package

For datasets that need custom download or load logic (auth, multi-file
extraction, schema injection), add a v0.5 dataset package under
`tabprep/datasets/<name>/`:

```
tabprep/datasets/my_dataset/
├── __init__.py             # imports downloader + loader (registers them)
├── downloader.py           # subclass HTTPArchiveDownloader / etc.
├── loader.py               # subclass BaseLoader; implement load()
└── README.md               # provenance, known issues, mirrors
```

The package autoloads at startup via `tabprep/datasets/__init__.py`
walking immediate subdirectories. Decorators (`@downloader("name")` /
`@loader("name")`) populate the registries.

See `tabprep/datasets/openml/` (small, simple) or
`tabprep/datasets/cic_apt_iiot/` (Kaggle mirror, custom loader) for
worked examples.

**Then create the profile YAML** that points at your package:

```yaml
downloader: my_dataset
loader: my_dataset
cached_at: raw/my_dataset/
loader_options: {}
```

---

## Code style

- **Formatter**: ruff defaults (line length 100). Run
  `ruff check tabprep tests`. CI rejects style violations.
- **Type hints**: Required for public functions and dataclasses.
- **Imports**: stdlib → third-party → first-party, blank line between
  groups. ruff's import sorter applies automatically.
- **No trailing whitespace, single trailing newline.**
- **Comments are for the reader five years from now.** Prefer
  self-explanatory code; add a comment when the *why* is non-obvious
  (a hidden constraint, a workaround, a subtle invariant).

---

## Commit message style

Match the existing commits (`git log --oneline`):

```
<area>: <short imperative summary, ≤72 chars>

<optional body explaining the why and any non-obvious mechanism.
Wrap at ~75 chars.>

Co-Authored-By: ...
```

Examples:

- `fix(loader): RAM-bounded loading for heavy IDS datasets`
- `feat(profiles): standardize 22 profiles for benchmarking`
- `fix(nbaiot,unsw_nb15): unblock end-to-end prepare on both datasets`

Avoid: trailing periods on the summary line, "WIP" or "checkpoint"
messages, unrelated changes lumped together.

---

## PR checklist

Before opening a PR:

- [ ] `ruff check tabprep tests` is clean.
- [ ] `pytest -q` is green.
- [ ] If you added/changed a profile: `tabprep prepare --profile <yours>`
      runs to completion and produces sensible row/class counts.
- [ ] If you added a new op or dataset package: it's registered via
      `@op` / `@loader` / `@downloader`, autoloaded, and has at least
      one smoke test.
- [ ] README, CONTRIBUTING, or `docs/*` updated where the change
      affects user-visible behaviour.
- [ ] No raw dataset bytes committed (large files belong on releases /
      Kaggle / Zenodo / S3, not git).

PR description should include:

- **What** changed and **why**.
- For new profiles: row counts, column counts, and class counts of
  the produced splits.
- Any upstream caveats (form gates, deprecated mirrors, etc.).

---

## What we won't merge

- **Auto-clean / heuristic cleaning ops** that try to guess the
  recipe for arbitrary tabular data. tabprep's design assumes the
  recipe is explicit. Auto-detection belongs in a future
  `init-profile` wizard.
- **Non-deterministic ops** that don't accept a seed.
- **Heavy optional dependencies** (pytorch, tensorflow, transformers)
  imported at module load time. If you need such a dep, import it
  inside the function so the rest of tabprep still works without it.
- **Profiles that don't follow the standardisation defaults** (no
  rebalancing, no scaling, drop ID columns, end with
  `stratified_fraction_sample`). Comparability across profiles is
  the whole point of the benchmark layer.
- **Squash-merging unrelated changes.** Keep PRs focused.

---

## Getting help

- Open an issue describing the dataset / op / source you'd like.
- For larger design questions, mention `@troisang1` in the issue.
- Security / sensitive reports: use GitHub's private vulnerability
  reporting on this repo.

Thanks again for contributing.
