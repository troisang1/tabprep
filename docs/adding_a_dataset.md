# Adding a new dataset

Two paths depending on whether the dataset is one we ship a profile for:

## (a) tabprep ships a profile

```bash
tabprep list                                    # see what's available
tabprep prepare --profile profiles/builtin/<name>.yaml
```

Default output: `../processed/<name>/` (when run from `cnNFST/data/tabprep`).
Override with `--output-root <path>`.

If the source needs a manual download (most IDS datasets), the profile
will tell you what URL to fetch and where to drop the file. The pipeline
verifies the file's SHA-256 before running anything else.

## (b) Bring your own dataset

For now (v0.1), copy a built-in profile and edit it:

```bash
cp profiles/builtin/pendigits.yaml profiles/user/my_data.yaml
# then edit:
#   - name / version / description
#   - source.kind  (sklearn | openml | url | manual)
#   - source.name / cached_at / sha256
#   - label.source_column   (the GT-class column in the raw file)
#   - pipeline (list of ops to clean the dataframe)
#   - split (defaults to 60/20/20 train/cal/test, seed 42)
```

Run it:

```bash
tabprep prepare --profile profiles/user/my_data.yaml
```

Copy the displayed sha256 values into the profile's `expected_hashes` and
re-run to confirm reproducibility:

```bash
tabprep verify --profile profiles/user/my_data.yaml
```

A future version will provide a wizard:

```bash
tabprep init-profile my_data --source path/to/raw.csv
```

which inspects the schema, suggests sensible default ops, and emits a
starter YAML. Not implemented in v0.1.

## Why each dataset needs its own pipeline

Tabular data has no universal preprocessing recipe. Network flow records,
UCI datasets, scRNA matrices, financial transactions — each has its own
column conventions (which columns leak identity, which are timestamps,
which categorical levels are sentinel `"-"`, which floats encode
booleans). The framework provides building blocks; the recipe is your job.
