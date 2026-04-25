# CIC-APT-IIoT-2024

**Source.** [UNB CIC — IIoT Dataset 2024 landing page](https://www.unb.ca/cic/datasets/iiot-dataset-2024.html)
**Citation.** UNB Canadian Institute for Cybersecurity, 2024 release. Please cite per the landing page.
**Licence.** CC-BY 4.0 (per UNB CIC standard terms).
**Distribution.** Form-gated: visit the landing page, complete the request form, UNB returns a one-time download token by email.

> **History.** UNB CIC restructured its hosting in 2025: the IP-based
> mirror at `cicresearch.ca` / `205.174.165.80` no longer serves
> direct download URLs (every request redirects to the landing
> index). Datasets are now distributed via per-request tokens. The
> framework's `cic_apt_iiot` downloader is therefore a polite
> refusal pointing the user at the landing page — auto-fetching
> isn't feasible.

## Licence consent

UNB CIC requires a one-time licence-consent form to be submitted before
each dataset is used. The form is informational — it tracks who's
using the dataset, not who has download access (the URL above is
public). The framework auto-submits it with the user's identity
(loaded from `TABPREP_USER_NAME`/`EMAIL`/`AFFILIATION`/`PURPOSE` env
vars).

**Please set these env vars** before running this profile in
production work:

```bash
export TABPREP_USER_NAME="Your Real Name"
export TABPREP_USER_EMAIL="you@your.institution.edu"
export TABPREP_USER_AFFILIATION="Your Institution"
export TABPREP_USER_PURPOSE="What you're using this dataset for"
```

If unset, the framework submits clearly-labelled placeholders and
prints a loud warning to stderr.

## Why this profile exists

CIC-APT-IIoT-2024 is the most recent CIC release we ship. It captures
the full Advanced-Persistent-Threat kill-chain (recon →
weaponisation → delivery → exploitation → installation →
command-and-control → actions) in an Industrial IoT testbed. Useful
because:

- Each row is labelled with the kill-chain stage, not just
  malicious/benign — finer-grained than the older CIC-IDS family.
- The IIoT context (Modbus, MQTT, OPC-UA flows) complements our
  enterprise-network coverage (CIC-IDS2018) and consumer-IoT coverage
  (CIC-IoT-2023).
- 2024 release date keeps the test corpus calibrated to current
  attacker tradecraft.

## Distribution layout

The ZIP extracts to several per-stage CSV files (exact layout varies
across upstream releases — typically one CSV per kill-chain stage
plus a manifest). The framework's `cic_apt_iiot` loader walks
recursively for `*.csv` and concatenates schema-tolerantly with utf-8
→ latin-1 → cp1252 encoding fallback.

## Reproducibility

```bash
export TABPREP_USER_NAME="..." TABPREP_USER_EMAIL="..." \
       TABPREP_USER_AFFILIATION="..." TABPREP_USER_PURPOSE="..."
tabprep prepare --profile cic_apt_iiot
```

`expected_hashes` is unset on first ship — pin them after the first
canonical run via `scripts/pin_hashes.py`.
