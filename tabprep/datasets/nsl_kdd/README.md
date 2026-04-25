# NSL-KDD

**Source.** [GitHub mirror — `defcom17/NSL_KDD`](https://github.com/defcom17/NSL_KDD)
**Citation.** Tavallaee, Bagheri, Lu & Ghorbani (2009). *A Detailed Analysis of the KDD CUP 99 Data Set*.
**Licence.** Open access; please cite the paper above.
**Direct downloads.** Four GitHub raw URLs (auto-fetched, ~25 MB total).

> **History.** UNB CIC's IP-based mirror at `205.174.165.80` /
> `cicresearch.ca` was the canonical distribution for NSL-KDD until
> ~2025, when UNB locked down direct download paths (every URL on
> those mirrors now redirects to the landing index). The
> well-maintained GitHub mirror is the de-facto canonical source as
> of 2026 and is what this profile fetches from.

## Why this profile exists

NSL-KDD is the cleaned-up KDD-99 distribution. The original KDD-99
(captured in 1998) had ~78% duplicate rows, which biased every model
trained on it. NSL-KDD removed those duplicates and re-balanced the
test set so 21 different KDD-99 classifiers all failed to perfectly
classify the held-out rows. The result is the **de-facto legacy IDS
baseline** still widely cited 16 years later.

Useful as a sanity check for any new IDS algorithm: the four attack
categories (`DoS`, `Probe`, `R2L`, `U2R`) are well-understood and the
features are simple (no IP addresses, no temporal leakage).

## Distribution layout

The ZIP extracts to:

```
NSL-KDD/
├── KDDTrain+.txt           — 125 973 rows, full training set
├── KDDTrain+_20Percent.txt —  25 192 rows
├── KDDTest+.txt            —  22 544 rows
├── KDDTest-21.txt          — rows where ≥21 KDD-99 classifiers failed
└── KDDTrain+.arff          — Weka ARFF export (skipped)
```

The framework concatenates `KDDTrain+.txt` + `KDDTest+.txt` and re-splits
via `stratified_class_balanced` so the split has classifier-friendly
class proportions. Authors who want the upstream's intentionally
hard-to-generalise split can pass `loader_options.use_files: [KDDTrain+.txt]`
to keep just the training file.

## Schema

41 features + 2 trailing columns:

- 9 categorical (`protocol_type`, `service`, `flag`, etc.)
- 32 numeric flow-derived features (`duration`, `src_bytes`, `count`, …)
- `label` — multi-class attack name (`back`, `buffer_overflow`,
  `ftp_write`, `guess_passwd`, `httptunnel`, `imap`, …)
- `difficulty` — NSL-KDD-specific 1–21 score; dropped by default
  (`loader_options.drop_difficulty: true`).

## Reproducibility

`tabprep prepare --profile nsl_kdd` from a clean tree:

1. Downloads `NSL-KDD.zip` (~5 MB) into `raw/nsl_kdd/`.
2. Extracts the four `.txt` files.
3. Reads + concats `KDDTrain+.txt` + `KDDTest+.txt` (148 517 rows total).
4. Drops the `difficulty` column.
5. Encodes categoricals (`protocol_type`, `service`, `flag`).
6. Stratified split → canonical CSV writer → SHA-256 manifest.

`expected_hashes` is unset on first ship — pin them after the first
canonical run via `scripts/pin_hashes.py`.
