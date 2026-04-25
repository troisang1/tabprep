# InSDN

**Source.** [Mendeley Data — InSDN dataset (DOI 10.17632/jxpfjc64kr.1)](https://data.mendeley.com/datasets/jxpfjc64kr/1)
**Citation.** Elsayed, Le-Khac & Jurcut (2020). *InSDN: A Novel SDN Intrusion Dataset*.
**Licence.** CC-BY 4.0
**Distribution.** Form-gated: per-file URLs are JS-rendered on the Mendeley page and rotate per browser session, so direct HTTP fetching by URL isn't feasible.

> **How to populate `raw/insdn/`:**
>
> 1. Visit the landing page and accept the CC-BY 4.0 licence.
> 2. Click "Download All" — Mendeley delivers a zip with the three
>    canonical CSVs (`Normal_data.csv`, `metasploitable-2.csv`,
>    `OVS.csv`).
> 3. Extract the zip into `raw/insdn/` and run
>    `tabprep prepare --profile insdn`.
>
> Alternative: the Kaggle mirror at
> `badcodebuilder/insdn-dataset` provides the same files if you have
> Kaggle API credentials configured (`~/.kaggle/kaggle.json`); the
> framework doesn't currently auto-fetch from Kaggle, but a future
> downloader could.

## Why this profile exists

Tabular IDS datasets historically focused on enterprise (CICIDS) or
IoT (Bot-IoT, IoT-23) network traffic. InSDN is the canonical
**Software-Defined Networking** intrusion dataset:

- **Three traffic sources:** benign (`Normal_data.csv`), exploit
  attacks via Metasploitable-2 (`metasploitable-2.csv`), and
  controller / control-plane attacks (`OVS.csv`).
- **SDN-specific features:** flow table entries, switch-controller
  messages, OpenFlow protocol fields not present in conventional NIDS
  feeds.
- Filling the gap between enterprise NIDS and emerging SDN/NFV
  deployments.

## Licence consent

Mendeley Data has a click-through licence form for each dataset. The
form is informational — once consented, the per-file download URLs
work without auth.

The framework auto-submits the form with the user's identity from
`TABPREP_USER_NAME` / `EMAIL` / `AFFILIATION` / `PURPOSE` env vars
(or placeholders + warning if unset). Please set these to your real
info before running this profile in production.

## URL stability

Mendeley sometimes rotates per-file URLs. The downloader's `urls`
tuple uses placeholder UUIDs that may not match the live distribution;
if a download 404s, visit the landing page and update the URLs in
`tabprep/datasets/insdn/downloader.py` to the current ones, then
re-pin `expected_hashes` after the next canonical run.

## Reproducibility

```bash
export TABPREP_USER_NAME="..." TABPREP_USER_EMAIL="..." \
       TABPREP_USER_AFFILIATION="..." TABPREP_USER_PURPOSE="..."
tabprep prepare --profile insdn
```

`expected_hashes` is unset on first ship — pin them after the first
canonical run.
