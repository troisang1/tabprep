# tabprep

[![CI](https://github.com/troisang1/tabprep/actions/workflows/ci.yml/badge.svg)](https://github.com/troisang1/tabprep/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A reproducible framework for preparing **tabular** datasets into ready-to-run
`train` / `calibration` / `test` CSVs from a single declarative profile.

> Same profile + same framework version + same source bytes = byte-identical
> output CSVs on every machine. Verified by SHA-256 manifests in every run.

---

## Why this exists

Most ML benchmarks ship a script (or several) that downloads, cleans, encodes,
splits, and saves a dataset. Those scripts drift, the seeds get forgotten, the
column order changes between runs, and reproducing a "published" dataset
becomes archaeology.

**tabprep replaces those scripts with a single executor and one profile YAML
per dataset.** The YAML records:

  - the source URL (with a checksum),
  - the ordered pipeline of cleaning ops,
  - the split parameters,
  - the **expected output hashes** of the final CSVs.

A maintainer locks the recipe by pinning hashes. A user then re-runs the
profile and either gets the same bytes (`tabprep verify` passes) or a clear
mismatch report. No more "did I configure this right?" — the framework tells
you.

---

## Built-in profiles (18 datasets)

The repo ships profile recipes for the [cnNFST / Hyper-NFST Track B
benchmark](https://github.com/troisang1/cnNFST) plus three additional
high-citation IDS datasets (CIC-DDoS-2019, CIC-IoMT-2024, IoT-23):

| Domain | Profiles |
|---|---|
| **UCI tabular** (8) | `pendigits`, `letter`, `optdigits`, `satimage`, `segment`, `texture`, `har`, `covertype` |
| **IDS network flows** (10) | `5g_nidd`, `ton_iot`, `nbaiot`, `edge_iiot`, `unsw_nb15`, `cicids2018`, `ciciot2023`, `cic_ddos2019`, `cic_iomt2024`, `iot23` |

UCI profiles auto-fetch from OpenML / sklearn (no manual download). IDS
profiles need a one-time manual download under `data/raw/<name>/` — the
profile tells you the URL and verifies the bytes via SHA-256 before any
preprocessing runs.

---

## Quickstart

```bash
git clone https://github.com/troisang1/tabprep.git
cd tabprep
pip install -e .

tabprep list                                       # list built-in profiles
tabprep prepare --profile pendigits                # by name (built-in lookup)
tabprep prepare --profile ./my_profile.yaml        # custom YAML
tabprep verify  --profile pendigits                # check pinned hashes match
tabprep prepare --all --source-kinds openml,sklearn  # whole UCI subset
tabprep verify  --all                                # verify everything
```

Default output goes to `./prepared/<dataset>/` (relative to the cwd);
override with `--output-root`. Default raw-data root is `./raw/`;
override with `--data-root`.

---

## How a profile is structured

Every profile is a single YAML file with this shape (v0.5 schema):

```yaml
name: pendigits
version: 1.0.0
description: Pen-based handwritten digits (10 classes, 16 features) — OpenML

# v0.5 schema: short downloader/loader names looked up in the
# tabprep.datasets registries. The downloader pre-fetches raw bytes
# (writes a `_complete` marker into cached_at); the loader assembles
# the (df, label_col) tuple.
downloader: openml                   # registered class name
loader: openml                       # registered class name
cached_at: raw/openml/pendigits/     # relative to --data-root
loader_options:
  openml_name: pendigits
  openml_version: 1                  # optional; defaults to 1

label:                               # how to identify the target
  source_column: label
  rename_to: label
  normalize: lowercase_underscore

pipeline:                            # ordered list of cleaning ops
  - op: rename_features_f0fN
  - op: filter_min_class_count
    min_count: 50

split:                               # train/cal/test partition
  kind: stratified_class_balanced
  train_frac: 0.5
  cal_frac:   0.1
  test_frac:  0.4
  seed: 42

output:                              # canonical-write parameters
  format: csv
  precision: 6
  column_sort: alphabetical          # alphabetical | source_order
  row_shuffle_seed: 42

expected_hashes:                     # pinned after the first canonical run
  train.csv:        9c978ee7e2090d…
  calibration.csv:  ecefce0dce8cc6…
  test.csv:         b3e7b3ff890bb0…
```

> **Migration note.** The v0.4 schema (`source: { kind, name, … }`) is
> still accepted — un-migrated profiles in `tabprep/profiles/builtin/`
> use it. v0.5's `downloader:`+`loader:` is preferred for new profiles
> (per-dataset packages under `tabprep/datasets/<name>/` with their
> own README, downloader, loader, and tests).

When you run `tabprep prepare` (or `tabprep.prepare(...)`), the executor:

1. **Auto-downloads** raw data into `cached_at/` via the registered
   `BaseDownloader` (idempotent — re-runs hit a cache marker).
2. Calls the registered `BaseLoader.load(cached_at, label_col, **loader_options)`,
   which returns a raw `(dataframe, label_column)` tuple.
3. Applies `rename_label` + `normalize_label_string` implicitly.
4. Applies the ops in `pipeline` in order — each op is a pure function
   `df → df`.
5. Calls the **split** function to partition into train / calibration / test.
6. Writes each split through the **canonical CSV writer**.
7. Computes SHA-256 of every output file and writes `_manifest.json`.
8. Cross-checks the observed hashes against `expected_hashes` (if pinned).
   Exits non-zero with a clear diff if they disagree.

---

## Reproducibility contract

Given the same profile, the same framework version, and the same source
bytes, `tabprep prepare` produces **byte-identical** output CSVs on every
machine. The contract is achieved by:

1. **Deterministic ops.** Every randomized op uses an explicit seed.
   `pandas.groupby(..., sort=True)` everywhere; never rely on insertion
   order. `set(...)` is forbidden in deterministic paths; we use
   `sorted(...)`.
2. **Deterministic encodings.** `pd.get_dummies` is fed `sorted(columns)`,
   so the encoded-column order is stable.
3. **Canonical CSV writer.** Sorts columns alphabetically (or
   `source_order` if explicitly opted in); sorts rows by per-row SHA-256
   then permutes by `row_shuffle_seed`; formats floats with
   `f"{x:.{precision}f}"` (no platform `%g`); uses `\n` line terminator;
   RFC4180-style minimal quoting.
4. **Source integrity.** When `source.sha256` is set, the raw download is
   hashed before any op runs. If the upstream changed, the pipeline
   aborts with a diff.
5. **Output manifest.** Every run writes a `_manifest.json` with file
   sizes, row counts, column counts, and SHA-256 hashes, plus the
   profile + framework versions.
6. **`expected_hashes` cross-check.** A profile with pinned hashes turns
   `tabprep prepare` into a verify-on-write: any drift produces a
   non-zero exit with a clear mismatch report.

---

## Built-in ops (catalog)

Every op has the signature `fn(df, *, label_col, **params) -> df`.

| Category | Op | Purpose |
|---|---|---|
| **Label** | `rename_label` | Rename `source_column` to `rename_to` (drops conflicts). |
| | `normalize_label_string` | `lowercase_underscore` or `none`. |
| **Cleaning** | `drop_columns` | Drop a named list (missing columns ignored). |
| | `drop_constant_columns` | Drop columns with a single unique value. |
| | `drop_constant_prefix_columns` | Drop constant columns whose name starts with given prefixes. |
| | `drop_ip_columns` | Drop common IP-address columns (network IDS leakage). |
| | `drop_high_nan_columns` | Drop columns with NaN ratio > `threshold`. |
| | `replace_inf` | Replace ±inf with NaN (or a numeric value). |
| | `fill_nan` | Fill NaN with a numeric constant. |
| | `coerce_numeric` | Convert non-label string columns to numeric. |
| | `strip_column_whitespace` | Strip leading/trailing whitespace from column names. |
| | `rename_columns` | Apply explicit `{old: new}` mapping. |
| | `filter_rows_label_isnull` | Drop rows where the label is NaN/empty/`'nan'`. |
| **Encoding** | `encode_categoricals` | One-hot encode low-cardinality strings; coerce mostly-numeric strings. |
| | `rename_features_f0fN` | Rename non-label columns to `f0..f(N-1)` in source order. |
| **Filtering** | `filter_min_class_count` | Drop rows whose label appears < `min_count` times. |
| | `drop_classes` / `keep_classes` | Filter rows by label name list. |
| **Sampling** | `cap_per_class` | Cap each class to at most N rows (deterministic). |
| | `balanced_subsample` | Cap dataset to ≤ `max_total` rows by per-class subsampling. |

---

## Built-in datasets and source kinds

**v0.5 dataset packages** (preferred — `tabprep/datasets/<name>/`):

| Package | Profiles | Downloader | Loader |
|---|---|---|---|
| `openml/` | `pendigits`, `letter`, `optdigits`, `satimage`, `segment`, `texture`, `har` | pre-fetches via `sklearn.datasets.fetch_openml` | reads name/version from `loader_options` |
| `covertype/` | `covertype` | pre-fetches via `sklearn.datasets.fetch_covtype` | normalises the as_frame / ndarray fallback |
| `iot23/` | `iot23` | direct download from Stratosphere CTU mirror | parses Zeek `conn.log.labeled` |

**v0.4 source kinds** (still in use for unmigrated profiles in
`tabprep/profiles/builtin/`; will be replaced by per-dataset packages
in Phase 4):

| Kind | Used by | What it does |
|---|---|---|
| `url` | `5g_nidd`, `ton_iot`, `edge_iiot` | Reads a single CSV from `cached_at`. SHA-256-checks if `source.sha256` is set. |
| `concat_csvs` | `cicids2018`, `ciciot2023`, `unsw_nb15`, `cic_ddos2019`, `cic_iomt2024` | Walks a directory tree recursively, concatenates every `*.csv` (case-insensitive). Encoding auto-falls through utf-8 → latin-1 → cp1252 per-file. |
| `nbaiot_dir` | `nbaiot` | Same as `concat_csvs` but derives the label from each file's basename (N-BaIoT convention). |
| `manual` | (custom) | Reads a single user-provided CSV; no integrity check. |

---

## Authoring a custom profile

**(a) Use a shipped loader.** Copy a built-in profile and adjust:

```bash
cp $(python -c "import tabprep, pathlib; \
print(pathlib.Path(tabprep.__file__).parent / 'profiles' / 'pendigits.yaml')") \
   ./my_data.yaml
$EDITOR ./my_data.yaml                  # adjust source / pipeline / split
tabprep prepare --profile ./my_data.yaml
# or, from Python:
result = tabprep.prepare("./my_data.yaml")
```

Then run [`scripts/pin_hashes.py`](scripts/pin_hashes.py) to bake the
observed SHA-256s back into the profile, and re-run `tabprep verify` to
confirm reproducibility.

**(b) New dataset package (v0.5).** Add a directory under
`tabprep/datasets/<name>/` with `downloader.py`, `loader.py`,
`__init__.py`, and a README. The package self-registers via
`@downloader("name")` / `@loader("name")` decorators when imported by
the autoloader at startup. See `tabprep/datasets/openml/` for a
fully-worked example.

**(c) New op.** Same pattern under `tabprep/ops/`:

```python
# tabprep/ops/your_op.py
import pandas as pd
from tabprep.ops._registry import op

@op("my_drop_zeros")
def my_drop_zeros(df, *, label_col, columns):
    keep = ~(df[columns].sum(axis=1) == 0)
    return df[keep].reset_index(drop=True)
```

Import it in `tabprep/ops/__init__.py`. The op is now usable from any
profile YAML.

**Note on universality.** Every dataset has its own column conventions —
which columns leak identity, which are timestamps, which sentinel values
encode missingness. tabprep gives you the building blocks; the recipe is
your job. There is no "auto-clean" mode.

---

## Project layout

```
tabprep/
├── LICENSE                            # Apache 2.0
├── README.md                          # this file
├── pyproject.toml                     # python package definition (ships profiles/*)
├── tabprep/                           # the package
│   ├── cli.py                         # `tabprep` shell entry point
│   ├── __main__.py
│   ├── core/
│   │   ├── profile.py                 # YAML loader + dataclass schema
│   │   ├── pipeline.py                # source → ops → split → write
│   │   ├── canonical.py               # byte-stable CSV writer
│   │   ├── splits.py                  # train/cal/test implementations
│   │   ├── manifest.py                # _manifest.json writer
│   │   ├── hashing.py                 # SHA-256 helpers
│   │   └── downloader.py              # generic HTTP fetch + extract
│   ├── ops/                           # registry-based ops
│   │   └── label.py / filter.py / clean.py / encode.py / sample.py
│   ├── datasets/                      # v0.5 per-dataset packages
│   │   ├── _base/                     # BaseDownloader + BaseLoader + registry
│   │   ├── openml/                    # 7-profile UCI family
│   │   ├── covertype/                 # standalone sklearn fetch
│   │   └── iot23/                     # Stratosphere CTU malware captures
│   ├── sources/                       # v0.4 source loaders (legacy, used by
│   │   │                              #                       unmigrated profiles)
│   │   └── url_source.py / concat_csvs_source.py / nbaiot_dir_source.py / …
│   └── profiles/                      # bundled profile YAMLs (ship with `pip install`)
│       ├── *.yaml                     # 9 v0.5 profiles
│       └── builtin/*.yaml             # 9 unmigrated v0.4 profiles
├── tests/                             # pytest suite (59 tests, 0 net deps)
├── docs/
│   └── DEVELOPMENT_LOG.md             # rolling per-phase handoff log
├── scripts/
│   └── pin_hashes.py                  # pins manifest hashes back into a profile
└── .github/workflows/ci.yml           # lint + test + UCI reproducibility
```

---

## Roadmap

- v0.1 ✅ scaffold + `pendigits` end-to-end (initial commit)
- v0.2 ✅ 8 UCI tabular profiles
- v0.3 ✅ 7 IDS profiles
- **v0.4** ✅ CI workflow (lint + test + UCI reproducibility)
- v0.5 — `tabprep init-profile` wizard, public release on PyPI
- v0.6 — Dockerfile, Hugging Face Hub publish

---

## Contributing

We welcome new profiles, new ops, new source kinds, and bug fixes.

See [**CONTRIBUTING.md**](CONTRIBUTING.md) for the full contributor guide:
local setup, test workflow, code style, the hash-pinning workflow when adding
a profile, and the PR review checklist.

Quick highlights:

- Every PR must pass `ruff check tabprep tests` and `pytest`.
- New profiles must include pinned `expected_hashes` and a passing
  `tabprep verify --profile <yours>` run.
- New ops/sources must register through `@op` / `@source` (no executor
  changes), and add at least one smoke test under `tests/`.
- Commit messages follow the style of existing commits (single
  imperative-mood summary line, blank line, longer body if needed).

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
