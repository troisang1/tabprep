# tabprep

A reproducible framework for preparing **tabular** datasets into ready-to-run
`train` / `calibration` / `test` CSVs from a single declarative profile.

> Same profile + same framework version + same source bytes = byte-identical
> output CSVs on every machine. Verified by SHA-256 manifests in every run.

## Why

Most ML benchmarks ship a script (or several) that downloads, cleans,
encodes, splits, and saves a CSV. The scripts drift, the seeds get
forgotten, the column order changes between runs, and reproducing a
"published" dataset becomes archaeology.

`tabprep` replaces those scripts with a single executor and one
**profile YAML per dataset**. The YAML records the source URL (with a
checksum), the ordered pipeline of cleaning ops, the split parameters,
and the **expected output hashes** of the final CSVs.

## Status

- **v0.1** (this commit): scaffolding + minimal end-to-end on `pendigits`
  (the simplest profile). Profile schema, op registry, canonical CSV
  writer, SHA-256 manifest, CLI stub.
- v0.2: port the 8 UCI tabular profiles (har, letter, optdigits, pendigits,
  satimage, segment, texture, covertype) used by the cnNFST/Hyper-NFST paper.
- v0.3: port the 7 IDS profiles (5g_nidd, ton_iot, nbaiot, cicids2018,
  ciciot2023, edge_iiot, unsw_nb15).
- v0.4: CI verifies all 15 profiles by hash on every commit.
- v0.5: Dockerfile, Hugging Face Hub publish, public release.

## Quickstart

```bash
# Inside an environment with python ≥ 3.10
pip install -e .

# List built-in profiles
tabprep list

# Prepare one (downloads if needed, splits, hashes)
tabprep prepare --profile profiles/builtin/pendigits.yaml

# Verify reproducibility against the profile's expected_hashes
tabprep verify --profile profiles/builtin/pendigits.yaml
```

Default output goes to `../processed/<dataset>/` (sibling to this repo
when it lives under `cnNFST/data/tabprep/`); override with
`--output-root <path>`.

## Authoring a custom profile

For datasets we do not ship, the framework cannot guess your cleaning
recipe — every dataset has its own column conventions. The intended UX is:

```bash
tabprep init-profile my_data --source path/to/raw.csv
# or
tabprep init-profile my_data --source-url https://example.org/x.csv
```

This inspects the schema (column names, dtypes, cardinality, NaN ratios)
and emits a starter YAML at `profiles/user/my_data.yaml` with sensible
default ops and `# TODO` markers for the parts you need to confirm
(label column, target precision, expected_hashes). Edit the YAML, then
run `tabprep prepare --profile profiles/user/my_data.yaml`.

## License

Apache 2.0 — see [LICENSE](LICENSE).
