# OpenML family

**Source.** [OpenML](https://www.openml.org/) (the public version 1 mirror of the original UCI tabular datasets).
**Fetch.** `sklearn.datasets.fetch_openml(name, version=1, as_frame=True, parser="auto")`.
**Licence.** Per-dataset on OpenML — typically CC-BY 4.0; verify on the upstream page.
**Cache.** sklearn writes raw OpenML bytes under `~/scikit_learn_data/`. tabprep treats `cached_at/_complete` as a sentinel marker for the dataset's availability.

## Datasets in this family

| Profile     | OpenML name | Classes | Features |
|-------------|-------------|---------|----------|
| `pendigits` | `pendigits` | 10      | 16       |
| `letter`    | `letter`    | 26      | 16       |
| `optdigits` | `optdigits` | 10      | 64       |
| `satimage`  | `satimage`  | 6       | 36       |
| `segment`   | `segment`   | 7       | 19       |
| `texture`   | `texture`   | 11      | 40       |
| `har`       | `har`       | 6       | 561      |

## Profile shape

```yaml
name: pendigits
downloader: openml
loader: openml
cached_at: raw/openml/pendigits/      # tail directory must equal openml_name
loader_options:
  openml_name: pendigits
  openml_version: 1                    # optional; default is 1
```

## Loader output

`OpenMLLoader.load(raw_dir, label_col, openml_name=..., openml_version=1)`
returns `(df, label_col)` where:

- `df = bunch.data.reset_index(drop=True).copy()`
- `df[label_col] = bunch.target.astype(str).reset_index(drop=True).values`

This shape matches the legacy `tabprep/sources/openml_source.py`
byte-for-byte, so migrated profiles reproduce the same canonical CSVs
(and the pinned `expected_hashes` keep matching).

## Downloader behaviour

`OpenMLDownloader.download(dest_dir)` warms sklearn's `~/scikit_learn_data/`
cache for the dataset whose name equals the tail of `dest_dir`, then
writes a `_complete` marker into `dest_dir`. Re-running on a populated
cache is a no-op (no network call).

The downloader always pre-fetches version 1; `loader_options.openml_version`
remains the source of truth at load time. A profile that pins a non-1
version will see a transient cache miss the first time the loader runs,
then sklearn caches that version too.

## Known issues

- **OpenML 301 redirect on `scikit-learn < 1.6`.** Older sklearn versions
  followed the OpenML 301 inconsistently; pin `scikit-learn>=1.5` (1.6+
  is more reliable) in CI to avoid intermittent fetch failures. tabprep
  itself works on either; the CI advisory job exists to catch upstream
  breakage early.

## Reproducibility

`tabprep prepare --profile <name>` (or `--profile tabprep/profiles/<name>.yaml`) from a clean tree:

1. Pre-fetches the OpenML bytes into `~/scikit_learn_data/`.
2. Loads via `fetch_openml(...)` — `(df, label)` shape pinned above.
3. Runs the cleaning pipeline (`rename_features_f0fN`, `filter_min_class_count`, …).
4. Stratified split → canonical CSV writer → SHA-256 manifest.

The pinned `expected_hashes` in each profile lock the recipe; subsequent
runs verify they match.
