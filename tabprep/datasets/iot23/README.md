# IoT-23

**Source.** [Stratosphere Laboratory, CTU Prague — IoT-23 dataset page](https://www.stratosphereips.org/datasets-iot23)
**License.** CC-BY 4.0
**Direct download.** `https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/iot_23_datasets_small.tar.gz` (lite distribution, Zeek logs only — no PCAPs).
**Citation.** Garcia, S., Parmisano, A., & Erquiaga, M. J. (2020). *IoT-23: A labeled dataset with malicious and benign IoT network traffic*.

## Distribution layout

The lite tarball (~9.4 GB) extracts to:

```
opt/Malware-Project/BigDataset/IoTScenarios/
├── CTU-Honeypot-Capture-4-1/bro/conn.log.labeled
├── CTU-Honeypot-Capture-5-1/bro/conn.log.labeled
├── CTU-IoT-Malware-Capture-1-1/bro/conn.log.labeled
├── CTU-IoT-Malware-Capture-3-1/bro/conn.log.labeled
... (23 capture folders total)
```

Each capture is one Zeek `conn.log.labeled` file containing flow-level
features and two trailing label columns (`label`, `detailed-label`).
Total ~325M flows; individual captures range from 32 KB to >10 GB.

## Format quirk

IoT-23's `conn.log.labeled` files use a **mixed tab/space layout**:

- The first 21 fields are tab-separated (standard Zeek output).
- The two trailing label columns (`label`, `detailed-label`) are
  appended **space-separated** within the last tab-token of the
  `#fields` header and every data row.

`IoT23Loader` handles this by parsing the `#fields` header with
whitespace-flattening and reading data rows with `sep=r"\s+"`.

## Drop columns (dataset-specific)

The profile drops:

- `ts` — flow start timestamp (capture-time leak).
- `uid` — Zeek-generated per-flow ID (random string, not a feature).
- `tunnel_parents` — set-typed metadata, almost always empty.

Generic ops handle the rest:

- IP address columns (`id.orig_h`, `id.resp_h`) → `drop_ip_columns`.
- Sentinel `-` values → parsed as NaN at load time, then `fill_nan`
  with 0 after numeric coercion.
- `service` and `proto` are categorical and one-hot encoded by
  `encode_categoricals`.

## Memory budget

The largest capture (`CTU-IoT-Malware-Capture-39-1`) has >100M flows;
loading every capture in full would OOM most machines. The profile
sets `loader_options.per_file_cap: 50000` so each capture contributes
its first 50k flows (head-N — deterministic for hash stability),
keeping the in-memory concat under ~1.2M rows before pipeline ops
finish narrowing it.

If you need a different memory budget, override
`loader_options.per_file_cap` in your local copy of the profile, but
note that doing so changes the output bytes — re-pin
`expected_hashes` after the first canonical run.

## Reproducibility

`tabprep prepare --profile iot23` (or `--profile tabprep/profiles/iot23.yaml`) from a clean tree:

1. Downloads the 9.4 GB tarball into `data/raw/iot23/`.
2. Extracts the 23 capture folders.
3. Reads + concats per the format quirk above.
4. Runs the cleaning pipeline (drop/encode/fillna/balanced subsample).
5. Stratified split → canonical CSV writer → SHA-256 manifest.

The pinned `expected_hashes` lock the recipe; subsequent runs verify
they match.
