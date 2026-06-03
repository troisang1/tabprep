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
### Preventing leakage (read this for any network/IDS dataset)

Leakage = a column that lets the model "cheat" by keying on identity or
recording conditions instead of traffic behaviour. It inflates benchmark
accuracy and collapses on any other network. There are **three distinct
kinds**, each with its own dedicated handling — do not improvise with a
generic `drop_columns`:

| Leak | How to remove it | What it catches / keeps |
|---|---|---|
| **Sibling labels** | `label.also_drop: [...]` in the **label block** | A dataset often ships several mutually-derived targets — pick one via `source_column`, list the rest here. Examples: Bot-IoT `attack`/`subcategory`, CIC-APT-IIoT `subLabel`/`subLabelCat`, UNSW-NB15 binary `Label`. A **per-device identity** column (N-BaIoT `DeviceName`) is also a label — it correlates with the attack family — so it goes here too, not in the features. |
| **IP / MAC addresses** | `op: drop_ip_columns` | Source/destination IP & MAC columns under *any* common naming (`saddr`/`daddr`, `Src IP`, `id.orig_h`, `SrcAddr`, `eth.src`, `*.hw_mac`, …) plus the CICFlowMeter `Flow ID` 5-tuple. **Ports are intentionally kept** — they are protocol behaviour, not host identity. Matching is name-normalised, so it won't clip look-alike features like NSL-KDD `dst_host_count` or `is_sm_ips_ports`. |
| **Timestamps** | `op: drop_timestamp_columns` | Absolute wall-clock capture time (`ts`, `Timestamp`, UNSW-NB15 `Stime`/`Ltime`, Edge-IIoT `frame.time`, …). Attacks are captured in fixed windows, so the clock alone separates classes. **Elapsed-time features are kept** — `duration`/`dur`, inter-arrival `*IAT*`, `flow_idle_time`/`flow_active_time`, `RunTime`, `TcpRtt`. |

`also_drop` runs *structurally* before your pipeline (you cannot forget
it), and both ops are name-normalised pattern matchers — you do **not**
need to know the exact column casing/separators upfront. For a column
that is genuinely dataset-specific and none of the above (free-text
payloads, row indices, capture-session counters like Bot-IoT `pkSeqID`),
use an explicit `op: drop_columns columns: [...]`.

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
