# Adding a dataset

Three paths, easiest first.

## (a) Use a built-in profile

```bash
tabprep list                                # see the 22 built-ins
tabprep prepare --profile nsl_kdd           # by name
```

Or from Python:

```python
import tabprep
train, cal, test = tabprep.load_splits("nsl_kdd")
```

The profile auto-downloads raw data into `raw/<name>/` on first run
and writes splits to `prepared/<name>/`. Subsequent runs hit the cache
unless you clear `raw/`.

## (b) Bring your own dataset

Copy a built-in profile that's structurally similar to your data,
then edit:

```bash
cp tabprep/profiles/builtin/nsl_kdd.yaml my_data.yaml
$EDITOR my_data.yaml
```

What you'll change:

- `name`, `version`, `description`
- `source.download_url` (or `download_urls`) and `archive_format`
- `cached_at` — where raw data is stored
- `label.source_column` — the column in the raw CSV holding the target
- `pipeline:` — the cleaning steps (drop ID columns, encode
  categoricals, fill NaN, etc.)

Run it:

```bash
tabprep prepare --profile ./my_data.yaml
# or, from Python:
result = tabprep.prepare("./my_data.yaml")
```

By convention, every profile ends its pipeline with the standard
benchmark slice:

```yaml
pipeline:
  # ... your cleaning ops ...
  - op: filter_min_class_count
    min_count: 50
  - op: stratified_fraction_sample      # 5% benchmark slice
    fraction: 0.05
    seed: 42
```

This produces a tractable, comparable subset that preserves class
proportions. Want the full thing? Set `fraction: 1.0`.

### What NOT to put in your pipeline

- **No scalers / normalisers.** Apply scaling at the model boundary,
  not in the data preparation layer. Different downstream models want
  different scaling, and stuffing one choice into the dataset prep
  layer makes the data less reusable.
- **No rebalancing** (`balanced_subsample`, `cap_per_class` for
  balance). Keep classes in their natural ratios — model evaluation
  metrics depend on it.
- **Drop label-adjacent columns.** If your dataset has both a binary
  `label` AND a multi-class `attack_cat`, drop the one you're NOT
  using as the target. Otherwise the model just memorises the
  redundant column. Use `op: drop_columns columns: [Label, ...]`.
- **Drop ID/identifier columns.** IPs, MACs, flow IDs, timestamps,
  capture-session counters — these are not features, they're
  metadata that leaks identity. Use `op: drop_ip_columns` for the
  common cases.

## (c) New v0.5 dataset package

For datasets that need bespoke logic (multi-file extraction, schema
injection for headerless CSVs, custom auth) — add a Python package
under `tabprep/datasets/<name>/`:

```
tabprep/datasets/my_dataset/
├── __init__.py             # imports downloader + loader
├── downloader.py           # subclass HTTPArchiveDownloader / etc.
├── loader.py               # subclass BaseLoader; implement load()
└── README.md               # provenance, mirrors, caveats
```

Then your profile YAML uses the new short names:

```yaml
downloader: my_dataset
loader: my_dataset
cached_at: raw/my_dataset/
loader_options: {}
```

See `tabprep/datasets/openml/` (small, simple) or
`tabprep/datasets/cic_apt_iiot/` (Kaggle mirror with custom loader)
for worked examples.

## Memory / RAM bounds for huge datasets

If your raw data is bigger than RAM (e.g. CIC-DDoS-2019 = 29 GB),
add `loader_options` with a per-file row cap and a memory budget:

```yaml
loader_options:
  max_rows_per_file: 200000             # head/reservoir/stratified per CSV
  sample_mode: stratified_by_label      # guarantees no class is dropped
  memory_budget_gb: 16                  # RSS ceiling; aborts before swap
```

`sample_mode` options:

- `head` — first N rows (cheapest; biased if the file is class-sorted).
- `reservoir` — uniform random across the file.
- `stratified_by_label` ⭐ — two-pass class-aware sample. Pass 1 reads
  only the label column to bin row indices; pass 2 keeps a
  proportional sample with floor=1 per class. **Every class with ≥1
  row in the file survives.**

The framework's `MemoryGuard` watches RSS between files and raises a
clear error if it crosses the budget — no surprise OOM-kills.

## Why each dataset needs its own pipeline

Tabular data has no universal preprocessing recipe. Network flow
records, UCI datasets, scRNA matrices, financial transactions —
each has its own column conventions (which columns leak identity,
which are timestamps, which categorical levels are sentinel `"-"`,
which floats encode booleans). The framework provides building
blocks; the recipe is your job.

## Pinning hashes (optional)

If you want your profile to enforce byte-identical reproduction:

```bash
tabprep prepare --profile my_data.yaml
python scripts/pin_hashes.py --profile my_data.yaml
tabprep verify --profile my_data.yaml          # must pass
```

Most of the standardised built-in profiles ship without
`expected_hashes` so they don't false-fail on minor pandas-version
drift. Pin only when you need a hard contract — for example, in a
published paper that cites a specific output.
