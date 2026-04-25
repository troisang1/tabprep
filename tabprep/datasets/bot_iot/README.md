# Bot-IoT

**Source.** [UNSW Canberra — Bot-IoT dataset](https://research.unsw.edu.au/projects/bot-iot-dataset)
**Citation.** Koroniotis, Moustafa, Sitnikova & Turnbull (2018). *Towards the Development of Realistic Botnet Dataset in the IoT*.
**Licence.** Research-use only (UNSW academic licence) — please cite the paper.
**Direct download.** AARNet Cloudstor (`cloudstor.aarnet.edu.au`).

## Why this profile exists

Bot-IoT is one of the most-cited IoT IDS datasets (>2k papers as of
2024). It complements our existing IoT coverage:

- **N-BaIoT** — botnet attacks against home IoT devices (Mirai/Bashlite).
- **IoT-23** — labelled Zeek captures from real IoT malware.
- **Bot-IoT** — botnet command-and-control + DDoS attacks; comprehensive
  multi-class taxonomy (DDoS, DoS, OS-fingerprint, Service-scan,
  Theft, Recon).

## Licence consent

UNSW gates Bot-IoT behind a click-through licence form for research
use. The framework auto-submits the form with the user's identity
loaded from `TABPREP_USER_NAME` / `EMAIL` / `AFFILIATION` / `PURPOSE`
env vars. Please set these to your real info — UNSW tracks
submissions.

```bash
export TABPREP_USER_NAME="Your Real Name"
export TABPREP_USER_EMAIL="you@your.institution.edu"
export TABPREP_USER_AFFILIATION="Your Institution"
export TABPREP_USER_PURPOSE="What you're using this dataset for"
```

If unset, the framework submits clearly-labelled placeholders and
prints a loud warning.

## Distribution variants

Two upstream variants:

- **Full distribution** (~16.7 GB): 74 partitioned CSVs covering
  every attack scenario in granular detail.
- **"10 best features" subset** (~70 MB, default): a single CSV with
  the 10 features that maximised classifier accuracy in the original
  paper. Used in most published Bot-IoT replications.

The shipped profile uses the 10-best-features subset by default —
small enough for CI runs, common enough to make published results
comparable. Override `BotIoTDownloader.url` for the full set.

## Schema

10-best-features columns (subset):

- `seq` — flow sequence number
- `stddev`, `mean`, `min`, `max`, `n_in_conn_p_srcip` — per-flow stats
- `state_number`, `drate`, `srate` — flow-state derivatives
- `category` — coarse multi-class label
- `subcategory` — fine multi-class label
- `attack` — binary label

The shipped profile uses `category` as the target.

## Reproducibility

```bash
export TABPREP_USER_NAME="..." TABPREP_USER_EMAIL="..." \
       TABPREP_USER_AFFILIATION="..." TABPREP_USER_PURPOSE="..."
tabprep prepare --profile bot_iot
```

`expected_hashes` is unset on first ship — pin them after the first
canonical run.
