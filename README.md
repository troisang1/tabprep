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
# Inside Python ≥ 3.10
git clone https://github.com/troisang1/tabprep.git
cd tabprep
pip install -e .

# List built-in profiles
tabprep list

# Prepare one (auto-downloads from OpenML for UCI profiles)
tabprep prepare --profile profiles/builtin/pendigits.yaml

# Verify reproducibility against the profile's pinned `expected_hashes`
tabprep verify --profile profiles/builtin/pendigits.yaml

# Prepare/verify the entire UCI subset (no manual download needed)
tabprep prepare --all --source-kinds openml,sklearn
tabprep verify --all --source-kinds openml,sklearn

# Verify everything (assumes prepare has been run for IDS profiles too)
tabprep verify --all
```

Default output goes to `../processed/<dataset>/` (sibling to this repo when
it lives under `cnNFST/data/tabprep/`); override with `--output-root`.

---

## How a profile is structured

Every profile is a single YAML file with this shape:

```yaml
name: pendigits
version: 1.0.0
description: Pen-based handwritten digits (10 classes, 16 features) — OpenML

source:                              # where the raw data comes from
  kind: openml                       # openml | sklearn | url | concat_csvs |
                                     # nbaiot_dir | manual
  name: pendigits

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

When you run `tabprep prepare`, the executor:

1. Calls the **source loader** for `source.kind`, which returns a raw
   `(dataframe, label_column)` tuple.
2. Applies `rename_label` + `normalize_label_string` implicitly.
3. Applies the ops in `pipeline` in order — each op is a pure function
   `df → df`.
4. Calls the **split** function to partition into train / calibration / test.
5. Writes each split through the **canonical CSV writer**.
6. Computes SHA-256 of every output file and writes `_manifest.json`.
7. Cross-checks the observed hashes against `expected_hashes` (if pinned).
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

## Built-in source kinds

| Kind | Used by | What it does |
|---|---|---|
| `openml` | UCI profiles | Calls `sklearn.datasets.fetch_openml(name, version=1)`. Pin a version with `name@<version>`. |
| `sklearn` | `covertype` | Built-in sklearn loaders (`fetch_covtype`, `fetch_kddcup99`, …). |
| `url` | `5g_nidd`, `ton_iot`, `edge_iiot` | Reads a single CSV from `cached_at`. SHA-256-checks if `source.sha256` is set. |
| `concat_csvs` | `cicids2018`, `ciciot2023`, `unsw_nb15`, `cic_ddos2019`, `cic_iomt2024` | Walks a directory tree recursively, reads every `*.csv` (case-insensitive extension), schema-tolerantly concatenates them. Encoding auto-falls through utf-8 → latin-1 → cp1252 per-file unless pinned via `source.url`. |
| `nbaiot_dir` | `nbaiot` | Same as `concat_csvs` but derives the label from each file's basename (N-BaIoT convention). |
| `zeek_conn_log` | `iot23` | Reads Zeek `conn.log.labeled` files (TSV with `#fields` header), recursive. |
| `manual` | (custom) | Reads a single user-provided CSV; no integrity check. |

---

## Authoring a custom profile

**(a) Use a built-in source.** Copy a built-in profile that uses a similar
source kind and edit:

```bash
cp profiles/builtin/pendigits.yaml profiles/user/my_data.yaml
$EDITOR profiles/user/my_data.yaml      # adjust source / pipeline / split
tabprep prepare --profile profiles/user/my_data.yaml
```

Then run [`scripts/pin_hashes.py`](scripts/pin_hashes.py) to bake the
observed SHA-256s back into the profile, and re-run `tabprep verify` to
confirm reproducibility.

**(b) New source kind.** Add a single file under `tabprep/sources/`:

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

Then add `from tabprep.sources import my_source  # noqa: F401` to
`tabprep/sources/__init__.py` so the registry sees it at import time. Now
`source.kind: my_kind` works in any profile.

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
├── pyproject.toml                     # python package definition
├── tabprep/                           # the package
│   ├── core/
│   │   ├── profile.py                 # YAML loader + dataclass schema
│   │   ├── pipeline.py                # source → ops → split → write
│   │   ├── canonical.py               # byte-stable CSV writer
│   │   ├── splits.py                  # train/cal/test implementations
│   │   ├── manifest.py                # _manifest.json writer
│   │   └── hashing.py                 # SHA-256 helpers
│   ├── ops/                           # registry-based ops
│   │   ├── label.py / filter.py / clean.py / encode.py / sample.py
│   ├── sources/                       # registry-based source loaders
│   │   ├── openml_source.py / sklearn_source.py / url_source.py
│   │   ├── concat_csvs_source.py / nbaiot_dir_source.py / manual.py
│   ├── cli.py                         # `tabprep` entry point
│   └── __main__.py
├── profiles/builtin/                  # 15 reference profile YAMLs
├── tests/                             # pytest suite
├── docs/
│   ├── design.md                      # architecture + determinism contract
│   └── adding_a_dataset.md            # how-to
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
