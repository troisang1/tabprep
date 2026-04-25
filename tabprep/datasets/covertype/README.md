# Covertype

**Source.** [UCI ML Repository — Forest Cover Type (Blackard 1998)](https://archive.ics.uci.edu/dataset/31/covertype)
**Fetch.** `sklearn.datasets.fetch_covtype(as_frame=True)`
**Licence.** CC-BY 4.0 (per the UCI archive page).
**Cache.** sklearn writes raw bytes under `~/scikit_learn_data/`. tabprep treats `cached_at/_complete` as a sentinel marker for the dataset's availability.

## Profile shape

```yaml
name: covertype
downloader: covertype
loader: covertype
cached_at: raw/covertype/
loader_options: {}
```

## Why standalone (not part of `openml/`)

`fetch_covtype` has a different signature than `fetch_openml`:

- No per-name argument; one fixed dataset.
- Older sklearn versions (`< 1.0`) silently return ndarray output even
  when `as_frame=True` is requested. The loader normalises both shapes
  and reconstructs feature names from `bunch.feature_names` (or
  `f0..fN-1` as a last resort).
- `fetch_covtype(as_frame=True)` itself raised `TypeError` on
  scikit-learn `< 0.24`. The downloader and loader both wrap the call
  in `try / except TypeError` and fall back to no-arg `fetch_covtype()`.

## Loader output

`CovertypeLoader.load(raw_dir, label_col)` returns `(df, label_col)`
matching the legacy `tabprep/sources/sklearn_source.py` byte-for-byte:

- `df = bunch.data.reset_index(drop=True).copy()` (or reconstructed
  DataFrame from ndarray output).
- `df[label_col] = pd.Series(bunch.target).astype(str).reset_index(drop=True).values`.

The migrated profile reproduces the same canonical CSVs as the legacy
path; pinned `expected_hashes` keep matching.

## Reproducibility

`tabprep prepare --profile covertype` (or `--profile tabprep/profiles/covertype.yaml`) from a clean tree:

1. Pre-fetches the covertype bytes into `~/scikit_learn_data/`.
2. Loads via `fetch_covtype(...)` — `(df, label)` shape pinned above.
3. Runs the cleaning pipeline (`rename_features_f0fN`,
   `filter_min_class_count`, `balanced_subsample max_total=10000`).
4. Stratified split → canonical CSV writer → SHA-256 manifest.

The pinned `expected_hashes` in `tabprep/profiles/covertype.yaml` lock the
recipe; subsequent runs verify they match.
