# Bot-IoT (5%-data subset)

**Distribution shipped.** 5%-data subset (~3.67 M rows) — **NOT** the full 72 M-row Bot-IoT.
**Source.** [Kaggle `vigneshvenkateswaran/bot-iot-5-data`](https://www.kaggle.com/datasets/vigneshvenkateswaran/bot-iot-5-data) (CC-BY).
**Citation.** Koroniotis, Moustafa, Sitnikova & Turnbull (2018). *Towards the Development of Realistic Botnet Dataset in the IoT*.
**Licence.** Research-use only (UNSW academic licence) — please cite the paper.
**Auto-fetch.** Kaggle public ZIP (~57 MB → 1 GB extracted, 4 reduced_data_*.csv).

> **What we ship vs. what UNSW publishes.** Bot-IoT has two upstream
> distributions: the **full** ~16.7 GB pcap+argus+csv corpus (~72 M
> rows) and the **5%-data** subset (~3.67 M rows). This profile uses
> the 5%-data subset because:
>
> - The full distribution's original AARNet Cloudstor host
>   (`cloudstor.aarnet.edu.au`) was decommissioned in 2023.
> - UNSW's SharePoint replacement returns HTTP 403 to non-browser
>   clients (session-bound cookie auth).
> - The IEEE DataPort mirror requires a paid subscription.
> - The Kaggle 5%-data mirror is the largest publicly auto-fetchable
>   variant, and is what the original paper and most replications cite.
>
> **If you need the full 72 M-row distribution**, you must download it
> manually from UNSW's research portal (browser-only) or IEEE DataPort
> (subscription) and place the pcap-derived argus/csv files under
> `raw/bot_iot/`. The framework's `cache_at` check will then skip the
> auto-download.

## Why this profile exists

Bot-IoT is one of the most-cited IoT IDS datasets (>2k papers). It
complements our existing IoT coverage:

- **N-BaIoT** — botnet attacks against home IoT devices (Mirai/Bashlite).
- **IoT-23** — labelled Zeek captures from real IoT malware.
- **Bot-IoT** — botnet command-and-control + DDoS attacks; comprehensive
  multi-class taxonomy (DDoS, DoS, Reconnaissance, Theft, Normal).

## Schema

The 5%-data CSVs have 46 columns including:

- 43 flow features (`seq`, `stddev`, `mean`, `min`, `max`,
  `state_number`, `drate`, `srate`, `Pkts_P_State_P_Protocol_*`, …)
- `attack` — binary label (1 = attack, 0 = benign)
- `category` — coarse multi-class label (used by this profile)
- `subcategory` — fine-grained label

Profile pipeline drops `pkSeqID`, `attack`, `subcategory` and uses
`category` as the multi-class target.

## Class distribution

The 5%-data subset preserves Bot-IoT's famously extreme class imbalance:

| Class | Approx. rows in 5%-data input |
|---|---|
| `DDoS` | ~1,700,000 |
| `DoS` | ~1,650,000 |
| `Reconnaissance` | ~91,000 |
| `Normal` | ~370 |
| `Theft` | ~80 |

After the profile's `balanced_subsample max_total: 1000000` (caps
each class to 200 K), the prepared output has ~492 K rows total
(120 K each of DDoS/DoS, ~55 K Reconnaissance, all of Normal/Theft).

## Reproducibility

```bash
tabprep prepare --profile bot_iot
```

No licence form, no env vars — Kaggle's public API serves the
mirror without authentication.

`expected_hashes` is unset on first ship — pin via
`scripts/pin_hashes.py` after the first canonical run.

## Pre-staged raw data

If you've already downloaded Bot-IoT (full or 5%-data) and want to
use those files directly without re-downloading, place the CSVs
under `raw/bot_iot/` and the framework's cache-hit check will skip
the network call. Files are read by the loader's recursive `*.csv`
glob, so any layout works as long as the CSVs are reachable.
