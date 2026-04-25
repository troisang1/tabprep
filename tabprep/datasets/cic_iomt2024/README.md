# CIC-IoMT-2024

**Source.** [UNB CIC — IoMT Dataset 2024](https://www.unb.ca/cic/datasets/iomt-dataset-2024.html)
**Mirror.** [Kaggle `zeynepdemirta/ciciomt2024-attacks`](https://www.kaggle.com/datasets/zeynepdemirta/ciciomt2024-attacks)
**Citation.** UNB Canadian Institute for Cybersecurity, 2024 release. Please cite per the landing page.
**Licence.** CC-BY 4.0 (per UNB CIC standard terms).
**Auto-fetch.** Kaggle public ZIP (~281 MB).

## Why this profile exists

CIC-IoMT-2024 captures Internet of Medical Things network attacks
(MQTT, TCP/IP, ARP-based) plus benign traffic. The dataset is
distributed by UNB CIC behind a 2025-locked-down request form — the
direct UNB mirror at `cicresearch.ca` redirects all paths to a
landing index. The Kaggle public mirror at
`zeynepdemirta/ciciomt2024-attacks` provides the same labelled attack
distribution as a ZIP; framework auto-fetches via Kaggle's
`/api/v1/datasets/download/...` endpoint (HEAD returns 404, GET
returns 200 — Kaggle quirk; framework uses GET).

## Distribution layout

The ZIP extracts to:

```
csv/
├── test/
│   ├── ARP_Spoofing_test.pcap.csv
│   ├── Benign_test.pcap.csv
│   ├── MQTT-DDoS-Connect_Flood_test.pcap.csv
│   ├── MQTT-DoS-Publish_Flood_test.pcap.csv
│   ├── Recon-Port_Scan_test.pcap.csv
│   ├── TCP_IP-DDoS-ICMP1_test.pcap.csv
│   ├── ... (21 files total per split)
│   └── TCP_IP-DoS-UDP_test.pcap.csv
└── train/
    └── ... (~25 files)
```

The CSVs have **no `label` column** — the attack class is encoded in
the filename. `CICIoMT2024Loader` derives the label by stripping
`.pcap` then `_test`/`_train` suffixes from the filename stem:

| Filename | Derived label |
|---|---|
| `ARP_Spoofing_test.pcap.csv` | `ARP_Spoofing` |
| `Benign_train.pcap.csv` | `Benign` |
| `MQTT-DDoS-Connect_Flood_test.pcap.csv` | `MQTT-DDoS-Connect_Flood` |
| `TCP_IP-DDoS-ICMP1_test.pcap.csv` | `TCP_IP-DDoS-ICMP1` |

## Schema notes

Per-file column sets vary slightly between MQTT and TCP/IP attack
families (MQTT payloads carry MQTT-specific features absent from
TCP/IP traffic). The loader uses `pd.concat(..., sort=False)` to
align columns schema-tolerantly; the framework's
`drop_high_nan_columns` step (default threshold 0.8) handles fields
present in only one family.

## Reproducibility

```bash
tabprep prepare --profile cic_iomt2024
```

`expected_hashes` is unset on first ship — pin them after the first
canonical run via `scripts/pin_hashes.py`.
