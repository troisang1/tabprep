# Contributing to tabprep

Thanks for considering a contribution. tabprep stays small and focused
on one promise — *same profile in, same bytes out* — so the bar for new
features is "does it serve the reproducibility contract?".

This guide covers:
- [Setup](#setup)
- [Running tests](#running-tests)
- [Code style](#code-style)
- [Adding a new profile](#adding-a-new-profile)
- [Adding a new op](#adding-a-new-op)
- [Adding a new source kind](#adding-a-new-source-kind)
- [The hash-pinning workflow](#the-hash-pinning-workflow)
- [PR checklist](#pr-checklist)
- [Commit message style](#commit-message-style)
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

## Running tests

```bash
pytest -q                                # smoke tests
pytest -q --cov=tabprep --cov-report=term  # with coverage

# Reproduce the UCI subset end-to-end
tabprep prepare --all --source-kinds openml,sklearn --output-root prepared
tabprep verify  --all --source-kinds openml,sklearn --output-root prepared
```

The IDS profiles need raw data at `data/raw/<name>/` — see each profile's
`source.url` for download instructions. Don't include the raw data in a PR.

---

## Code style

- **Formatter**: ruff defaults (line length 100). Run `ruff check tabprep
  tests`. CI rejects style violations.
- **Type hints**: Required for public functions and dataclasses.
  Optional but encouraged inside ops.
- **Imports**: stdlib → third-party → first-party, blank line between
  groups. ruff's import sorter applies automatically.
- **No trailing whitespace, single trailing newline.**
- **No emojis** in code or docstrings unless the user-facing CLI message
  benefits clearly. Comments are written for the contributor reading the
  code five years from now, not for personality.

---

## Adding a new profile

The most common contribution. The recipe:

1. **Find a source.** Try OpenML first via `kind: openml` (cheapest;
   auto-downloaded in CI). Falls back to `sklearn` for the few datasets
   built into scikit-learn (covertype, kddcup99). For data that needs a
   manual download, use `kind: url` with `cached_at: raw/<name>/...` and
   set `source.sha256` to the file's SHA-256 (use `shasum -a 256 <file>`
   to compute it).
2. **Copy a similar built-in profile** as a starting point:

   ```bash
   cp profiles/builtin/pendigits.yaml profiles/builtin/my_dataset.yaml
   $EDITOR profiles/builtin/my_dataset.yaml
   ```

3. **Decide the cleaning recipe.** Open the raw data and figure out:
   - Which columns are identity-leaking (IPs, MACs, hostnames)?
   - Which are timestamps?
   - Which are sentinel-only (a single `"-"` everywhere)?
   - Which are categorical and worth one-hot encoding?
   - Which are mostly numeric strings that need `coerce_numeric`?

   Express the answers as an ordered `pipeline:` list. Re-use the
   built-in ops first; only add a new op if no combination of existing
   ones does the job.
4. **Pick a split.** Default is `stratified_class_balanced` 50/10/40
   (UCI convention) or 60/20/20 (IDS convention). Override fractions in
   the `split:` block if your dataset's downstream consumer needs a
   different shape.
5. **Run prepare + pin hashes:**

   ```bash
   tabprep prepare --profile profiles/builtin/my_dataset.yaml
   python scripts/pin_hashes.py --profile profiles/builtin/my_dataset.yaml
   tabprep verify --profile profiles/builtin/my_dataset.yaml      # must pass
   ```

6. **Add a smoke test** under `tests/test_profiles_my_dataset.py`:
   load the profile and assert `name`, `source.kind`, and at least one
   pipeline op's presence. Don't run the full preparation in unit tests
   (that's the reproducibility job in CI).
7. **Update the README** — add your dataset to the "Built-in profiles
   (15 datasets)" table.
8. **Open a PR** following the [checklist](#pr-checklist).

If your dataset has license / redistribution constraints, document them
in the profile's `description` field and link to the original source.
Don't commit raw data files.

---

## Adding a new op

Add a single file under `tabprep/ops/` and register the function with
the `@op` decorator:

```python
# tabprep/ops/my_op.py
import pandas as pd
from tabprep.ops._registry import op

@op("my_drop_zeros")
def my_drop_zeros(df: pd.DataFrame, *, label_col: str,
                  columns: list[str]) -> pd.DataFrame:
    """Drop rows whose values across `columns` sum to zero.

    Useful for IDS data where a degenerate flow has every byte/packet
    counter == 0.
    """
    keep = ~(df[columns].sum(axis=1) == 0)
    return df[keep].reset_index(drop=True)
```

Then add `import tabprep.ops.my_op  # noqa: F401` to `tabprep/ops/__init__.py`
so the registry sees it.

**Op contract:**

- Signature: `fn(df: pd.DataFrame, *, label_col: str, **params) -> pd.DataFrame`.
  All params are keyword-only and match the YAML keys verbatim.
- Pure. Don't mutate `df`; return a new dataframe.
- Deterministic. If the op is randomized (subsample, shuffle), accept a
  `seed: int` param and use `random_state=seed`.
- Idempotent where it makes sense (drops are idempotent; renames are
  not).
- One concept per op. If your op needs a 100-line docstring to explain
  itself, it's probably two ops.

**Test it.** Add a test under `tests/test_ops_my_op.py`:

```python
import pandas as pd
from tabprep.ops import OP_REGISTRY

def test_my_drop_zeros_keeps_nonzero_rows():
    df = pd.DataFrame({"a": [0, 1, 0], "b": [0, 2, 0], "label": ["x", "y", "z"]})
    out = OP_REGISTRY["my_drop_zeros"](df, label_col="label", columns=["a", "b"])
    assert list(out["label"]) == ["y"]
```

---

## Adding a new source kind

Same registry pattern under `tabprep/sources/`:

```python
# tabprep/sources/my_source.py
import pandas as pd
from tabprep.core.profile import SourceSpec
from tabprep.sources._registry import source

@source("my_kind")
def load_my(spec: SourceSpec, label: str) -> tuple[pd.DataFrame, str]:
    """Read from <wherever>; return (df, label_column)."""
    df = ...
    return df, label
```

Add the import to `tabprep/sources/__init__.py`. The new kind is
immediately usable as `source.kind: my_kind` in any profile.

**Source contract:**

- Returns `(df, label_column)`. The label column may already be
  populated in the dataframe, OR the source may add it (e.g. from a
  filename pattern). The string returned is the column name; downstream
  ops use it as `label_col`.
- Honour `source.sha256` if your kind reads a single file. Skip
  integrity checking for multi-file sources unless the profile has a
  manifest format for that.
- Fail loudly. If the source is missing or corrupt, raise with a
  message that tells the user where to download it from.

---

## The hash-pinning workflow

A profile becomes "reproducible" the moment you pin its `expected_hashes`.
The workflow:

```bash
# 1. Run the profile end-to-end (writes <output-root>/<name>/_manifest.json)
tabprep prepare --profile profiles/builtin/my_dataset.yaml

# 2. Read the manifest's SHA-256s back into the profile
python scripts/pin_hashes.py --profile profiles/builtin/my_dataset.yaml

# 3. Verify the pin: re-running should now report "expected_hashes match"
tabprep prepare --profile profiles/builtin/my_dataset.yaml      # exit 0
tabprep verify  --profile profiles/builtin/my_dataset.yaml      # exit 0
```

If a future framework change breaks reproducibility (e.g. a new pandas
version writes floats slightly differently), CI will catch it via the
UCI reproducibility job, and we'll bump the framework version + re-pin
all hashes in a single coordinated commit.

If your PR changes a built-in profile's expected output, you must also
re-pin that profile's hashes and call out the change in your PR
description. Reviewers verify the new hashes are intentional.

---

## PR checklist

Before opening a PR:

- [ ] `ruff check tabprep tests` is clean.
- [ ] `pytest -q` is green on Python 3.11 (CI tests 3.10–3.12 too).
- [ ] If you added/changed a profile: `tabprep verify --profile <yours>`
  passes, and the profile carries pinned `expected_hashes`.
- [ ] If you added a new op or source kind: it's registered via `@op` /
  `@source`, imported in the corresponding `__init__.py`, and has at
  least one smoke test.
- [ ] README, CONTRIBUTING, or `docs/*` updated where the change affects
  user-visible behaviour.
- [ ] No raw dataset bytes committed (large files belong in releases /
  S3 / Hugging Face, not git).

PR description should include:

- **What** changed and **why**.
- A `tabprep verify --all` snippet, or specific profiles affected.
- For new profiles: row counts, column counts, and class counts of
  outputs. (Run-time and output size are nice-to-have.)

---

## Commit message style

Match the existing commits (`git log --oneline`):

```
<area>: <short imperative summary line, ≤72 chars>

<optional 1–3 paragraph body explaining the why and any non-obvious
mechanism. Wrap at ~75 chars.>

Co-Authored-By: ...
```

Examples:

- `v0.3: 7 IDS network-flow profiles (5g_nidd, ton_iot, ...)`
- `ops: rename_label drops conflicting target column to avoid duplicates`
- `cli: add --all flag to prepare and verify`
- `fix: filter_min_class_count when label col is renamed in pipeline`

Avoid: trailing periods on the summary line, unrelated changes lumped
together, "WIP" or "checkpoint" messages.

---

## What we won't merge

- **Auto-clean / heuristic cleaning ops** that try to guess the right
  recipe for arbitrary tabular data. tabprep's design assumes the
  recipe is explicit. If you want auto-detection, that belongs in the
  `init-profile` wizard (planned for v0.5).
- **Non-deterministic ops** that don't accept a seed.
- **Ops or sources that import a heavy optional dependency** (pytorch,
  tensorflow, hugging-face transformers) at module load time. If you
  need such a dep, import it inside the function so the rest of tabprep
  still works without it.
- **Profiles that don't pin `expected_hashes`.** A profile without
  hashes is not reproducible; it's just a script.
- **Squash-merging unrelated changes.** Keep PRs focused.

---

## Getting help

- Open an issue describing the dataset / op / source you'd like.
- For larger design questions, mention `@troisang1` in the issue.
- Security / sensitive reports: use GitHub's private vulnerability
  reporting on this repo.

Thanks again for contributing.
