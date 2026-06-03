# tabprep

[![CI](https://github.com/troisang1/tabprep/actions/workflows/ci.yml/badge.svg)](https://github.com/troisang1/tabprep/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**One line of Python → train / calibration / test DataFrames for 15+ benchmark
datasets.** No tuning, no manual download, no `~/.cache` archaeology.

```python
import tabprep

train, cal, test = tabprep.load_splits("nsl_kdd")    # done.
```

That's the contract. tabprep handles the download, the cleaning, the
encoding, the split, and the byte-stable canonical write — the same
inputs always produce the same output bytes on every machine.

---

## Get started in 30 seconds

```bash
pip install -e .
```

```python
import tabprep

# 1. Train/cal/test in one call (downloads on first use, cached after)
train, cal, test = tabprep.load_splits("nsl_kdd")

# 2. Or get the full result with paths + verification status
result = tabprep.prepare("nsl_kdd")
print(result.output_dir)        # ./prepared/nsl_kdd/
train = result.load("train")    # → pd.DataFrame

# 3. List what's available
for prof in tabprep.list_profiles():
    print(prof.name, "—", prof.description.splitlines()[0])
```

Every dataset arrives as a **5% stratified subset** by default — a
size that runs experiments in seconds while preserving every class
in the source distribution. Need the full thing? Edit one line in
the profile YAML (`fraction: 0.05` → `fraction: 1.0`).

---

## What you get out of the box

15+ ready-to-go datasets with no manual download:

| Family | Datasets | Source |
|---|---|---|
| **Network IDS — IoT** | `5g_nidd`, `bot_iot`, `ciciot2023`, `cic_iomt2024`, `iot23`, `nbaiot`, `ton_iot` | Kaggle / Stratosphere / UCI mirrors |
| **Network IDS — enterprise** | `cicids2018`, `cic_ddos2019`, `cic_apt_iiot`, `unsw_nb15`, `nsl_kdd`, `edge_iiot`, `insdn` | UNB CIC / Zenodo / Kaggle |
| **UCI tabular** | `pendigits`, `letter`, `optdigits`, `satimage`, `segment`, `texture`, `har`, `covertype` | OpenML / sklearn |

> **Heads-up.** OpenML's API server has had an HTTP-301 self-redirect bug
> since Apr 2026; the 7 OpenML profiles can't auto-fetch until upstream
> fixes it. The 15 IDS profiles all work today.

Each profile downloads from a *public* mirror (Kaggle, Zenodo, sklearn,
direct UCI). No licence form. No SharePoint auth. No "request access".

---

## What every profile guarantees

Out of the box, every profile applies these defaults so your benchmark
results are comparable across datasets:

| Standardisation | What it does |
|---|---|
| **5% stratified subsample** | Tractable size; preserves class proportions; tiny classes survive (floor=1). |
| **No rebalancing** | Classes stay in their natural ratios — no synthetic balance. |
| **No scaling / normalisation** | Raw feature values are preserved. Apply your own scaler at the model boundary if you need one. |
| **IP / MAC columns dropped** | `drop_ip_columns` removes source/destination IP & MAC addresses and the CICFlowMeter `Flow ID` 5-tuple — a model must not cheat by memorising *which host* attacked. Ports are deliberately **kept** (they carry protocol behaviour, not host identity). |
| **Timestamps dropped** | `drop_timestamp_columns` removes absolute capture-clock columns (e.g. UNSW-NB15 `Stime`/`Ltime`, CIC `Timestamp`, Zeek `ts`) so a model can't separate classes by *when* traffic was recorded. Elapsed-time / inter-arrival features (`duration`, `*IAT*`, idle/active) are kept. |
| **One label column** | A dataset may ship several mutually-derived targets — binary + multi-class + sub-labels (e.g. CIC-APT-IIoT `label`/`subLabel`/`subLabelCat`), or a per-device identity (N-BaIoT). The profile picks one via `label.source_column`; every sibling target is listed in `label.also_drop` and removed before the pipeline so it can't leak the answer. |
| **RAM-bounded loading** | Large datasets (cic_ddos2019 = 29 GB raw) load with per-file caps and a memory watchdog so the process never OOMs. |
| **Class-aware sampling** | Per-file row caps use a two-pass `stratified_by_label` mode that guarantees no minority class is silently dropped. |

Want the full dataset, no subsampling, no encoding? Override per-profile
in YAML — every default is one line.

---

## Common recipes

### Just give me DataFrames

```python
train, cal, test = tabprep.load_splits("ciciot2023")
```

### I want the full dataset, not 5%

Copy the profile and bump the fraction:

```bash
cp $(python -c "import tabprep, pathlib; print(pathlib.Path(tabprep.__file__).parent / 'profiles/builtin/ciciot2023.yaml')") my_ciciot2023.yaml
```

Edit `fraction: 0.05` → `fraction: 1.0` (the last op in the pipeline) and:

```python
result = tabprep.prepare("./my_ciciot2023.yaml")
```

### I want my own dataset

```python
result = tabprep.prepare("./my_profile.yaml")
```

See [`docs/adding_a_dataset.md`](docs/adding_a_dataset.md) for the
profile YAML format. Or copy a built-in profile and edit.

### CLI alternative

```bash
tabprep list                                # 22 profiles
tabprep prepare --profile nsl_kdd           # by name
tabprep prepare --profile ./my.yaml         # custom YAML
tabprep prepare --all                       # everything (~30 min, ~3 GB)
tabprep verify  --profile nsl_kdd           # check pinned hashes match
```

Outputs land in `./prepared/<name>/` by default. Override with
`--output-root` (CLI) or `output_dir=` (Python API).

---

## Reproducibility — same input → same bytes

Every profile that pins `expected_hashes` becomes a verify-on-write
contract: rerun the prepare and either get the same bytes or a clear
mismatch report.

```python
result = tabprep.prepare("nsl_kdd")
result.verified                  # True if all output hashes match the pin
```

Behind the scenes:

- **Deterministic ops.** Every randomized op (sampling, shuffle) takes
  an explicit seed.
- **Canonical CSV writer.** Columns sorted alphabetically; rows sorted
  by per-row SHA-256 then permuted by `row_shuffle_seed`; floats
  formatted with fixed precision (no platform `%g`); `\n` line
  terminator; RFC-4180 minimal quoting.
- **Source integrity.** Raw downloads are SHA-256-checked when a
  hash is pinned in the profile.
- **Manifest.** Every run writes `_manifest.json` with file sizes,
  row/column counts, SHA-256 hashes, profile name, and framework
  version.

---

## Profile YAML in 30 seconds

```yaml
name: my_dataset
version: 1.0.0
description: One-line description.

# Where the raw data comes from (one of three patterns)
downloader: openml                      # for the simple cases
loader: openml
cached_at: raw/openml/my_dataset/
loader_options:
  openml_name: my_dataset

label:
  source_column: label                  # the column holding the target
  rename_to: label
  normalize: lowercase_underscore
  # also_drop: [other_label, sub_label]  # sibling targets to remove (anti-leakage)

pipeline:                               # ordered cleaning ops
  - op: drop_ip_columns                 # drop IPs / MACs / Flow ID (anti-leakage)
  - op: drop_timestamp_columns          # drop wall-clock timestamps (anti-leakage)
  - op: encode_categoricals
    max_cardinality: 50
    method: onehot
  - op: coerce_numeric
  - op: replace_inf
  - op: fill_nan
    value: 0
  - op: filter_min_class_count
    min_count: 50
  # Standardised 5% stratified slice — preserves class proportions.
  - op: stratified_fraction_sample
    fraction: 0.05
    seed: 42

split:
  kind: stratified_class_balanced
  train_frac: 0.6
  cal_frac:   0.2
  test_frac:  0.2
  seed: 42

output:
  format: csv
  precision: 6
  column_sort: alphabetical
  row_shuffle_seed: 42
```

That's the entire schema for a v0.5 profile. Drop it in any directory and
point `tabprep.prepare(...)` at it.

---

## Built-in ops (cheatsheet)

Every op has the signature `fn(df, *, label_col, **params) -> df`.

| Category | Op | What it does |
|---|---|---|
| **Cleaning** | `drop_columns` | Drop a named list (missing columns ignored). |
| | `drop_ip_columns` | Drop IP/MAC address columns + CICFlowMeter `Flow ID` (identity leakage). Name-normalised match; ports are **not** dropped. |
| | `drop_timestamp_columns` | Drop absolute wall-clock timestamp columns (temporal leakage). Keeps duration / IAT / idle-active timing features. |
| | `drop_high_nan_columns` | Drop columns with NaN ratio > `threshold`. |
| | `drop_constant_columns` | Drop columns with a single unique value. |
| | `replace_inf` | Replace ±inf with NaN. |
| | `fill_nan` | Fill NaN with a numeric constant. |
| | `coerce_numeric` | Convert string-numeric columns to numeric dtype. |
| | `strip_column_whitespace` | Strip leading/trailing whitespace from column names. |
| **Encoding** | `encode_categoricals` | One-hot encode low-cardinality strings. |
| | `rename_features_f0fN` | Rename non-label columns to `f0..f(N-1)`. |
| **Filtering** | `filter_rows_label_isnull` | Drop rows with null label. |
| | `filter_min_class_count` | Drop rows in classes appearing < `min_count` times. |
| | `drop_classes` / `keep_classes` | Filter rows by label-name list. |
| **Sampling** | `stratified_fraction_sample` ⭐ | Take `fraction` of each class — preserves proportions. **The new default.** |
| | `cap_per_class` | Cap each class to ≤ N rows. |
| | `balanced_subsample` | Cap dataset to ≤ `max_total` rows by per-class subsampling (rebalances). |

---

## Authoring your own dataset

The full guide lives at [`docs/adding_a_dataset.md`](docs/adding_a_dataset.md).
TL;DR three options, easiest first:

1. **Copy + edit a built-in profile.** No code, just YAML.
2. **Add a custom op.** Drop a Python file under `tabprep/ops/` with a
   `@op("name")` decorator. Now usable from any profile.
3. **Add a v0.5 dataset package.** Full custom downloader + loader for
   datasets that need bespoke logic. See `tabprep/datasets/openml/`.

---

## Memory & speed for huge datasets

The largest IDS profiles (`cic_ddos2019` = 29 GB raw, `ciciot2023` = 6
GB raw) ship with a built-in **RAM guard** so the loader never OOMs.
Two knobs control it:

```yaml
loader_options:
  max_rows_per_file: 200000             # head/reservoir/stratified per CSV
  sample_mode: stratified_by_label      # "head" | "reservoir" | "stratified_by_label"
  memory_budget_gb: 16                  # RSS ceiling; aborts before swap
```

`sample_mode: stratified_by_label` uses a two-pass class-aware scan:
pass 1 reads only the label column to bin row indices, pass 2 keeps a
proportional class-stratified sample. **Every class with ≥1 row in the
file survives** even when the file is much larger than `max_rows_per_file`.

When unset, the watchdog defaults to 80% of detected total RAM and
raises `RAMBudgetExceeded` with an actionable message before the OS
starts swapping.

---

## Project layout

```
tabprep/
├── tabprep/
│   ├── api.py                      # public Python API (prepare / load_splits)
│   ├── cli.py                      # `tabprep` shell entry point
│   ├── core/
│   │   ├── profile.py              # YAML loader + dataclass schema
│   │   ├── pipeline.py             # source → ops → split → write
│   │   ├── canonical.py            # byte-stable CSV writer
│   │   ├── memguard.py             # RAM watchdog (per-loader RSS ceiling)
│   │   └── …
│   ├── ops/                        # registry-based pipeline ops
│   ├── datasets/                   # per-dataset downloaders + loaders
│   │   ├── _base/                  # BaseDownloader + BaseLoader + sampling
│   │   ├── openml/, covertype/, iot23/, cic_apt_iiot/, …
│   ├── sources/                    # legacy v0.4 source loaders
│   └── profiles/                   # bundled profile YAMLs
│       ├── *.yaml                  # v0.5 profiles
│       └── builtin/*.yaml          # v0.4 profiles (still supported)
├── tests/                          # pytest suite (295+ tests)
├── examples/quickstart.py          # five canonical Python API patterns
├── docs/
│   ├── adding_a_dataset.md         # how to add your own
│   ├── design.md                   # architecture overview
│   └── DEVELOPMENT_LOG.md          # rolling per-phase changelog
└── scripts/pin_hashes.py           # bake manifest hashes back into a profile
```

---

## Contributing

We welcome new profiles, new ops, new dataset packages, and bug fixes.
The bar for new features is "does it serve the reproducibility
contract?".

See [**CONTRIBUTING.md**](CONTRIBUTING.md) for the contributor guide.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
