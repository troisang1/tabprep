"""CIC-IoMT-2024 loader: filename-encoded labels.

The Kaggle mirror's CSVs have **no `label` column** — the attack
class is encoded in the filename. Files follow the pattern:

    csv/test/<AttackName>_test.pcap.csv
    csv/train/<AttackName>_train.pcap.csv

where `<AttackName>` is one of:

    ARP_Spoofing, Benign, MQTT-DDoS-Connect_Flood,
    MQTT-DDoS-Publish_Flood, MQTT-DoS-Connect_Flood,
    MQTT-DoS-Publish_Flood, MQTT-Malformed_Data, Recon-OS_Scan,
    Recon-Ping_Sweep, Recon-Port_Scan, Recon-VulScan,
    TCP_IP-DDoS-{ICMP1..5,SYN,TCP,UDP1..2}, TCP_IP-DoS-{ICMP,SYN,TCP,UDP}

`CICIoMT2024Loader.load(...)` walks the cache directory recursively,
parses each `*.pcap.csv`, derives the label from the filename, and
concatenates schema-tolerantly (some files have slightly different
column sets between MQTT and TCP/IP attacks).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from tabprep.datasets._base import BaseLoader, loader


def _label_from_filename(stem: str) -> str:
    """Derive the attack label from a CIC-IoMT-2024 CSV filename stem.

    Strips a trailing `.pcap` (since the file extension is `.csv` but
    the name ends `.pcap.csv`), then strips a trailing `_test` or
    `_train` partition marker.

    Examples:
        ARP_Spoofing_test.pcap   → ARP_Spoofing
        TCP_IP-DDoS-ICMP1_train.pcap → TCP_IP-DDoS-ICMP1
        Benign_test.pcap         → Benign
    """
    # Strip ".pcap" if present — pathlib.Path.stem only strips one extension,
    # so "ARP_Spoofing_test.pcap.csv".stem = "ARP_Spoofing_test.pcap".
    if stem.endswith(".pcap"):
        stem = stem[:-len(".pcap")]
    for suffix in ("_test", "_train"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    return stem


@loader("cic_iomt2024")
class CICIoMT2024Loader(BaseLoader):
    """Reader for CIC-IoMT-2024 per-attack `.pcap.csv` files.

    Profile usage:
        loader: cic_iomt2024
        loader_options:
          glob: "*.pcap.csv"            # default
    """

    DEFAULT_GLOB: str = "*.pcap.csv"

    def load(
        self,
        raw_dir: Path,
        label_col: str,
        *,
        glob: str | None = None,
        **opts: Any,
    ) -> tuple[pd.DataFrame, str]:
        pattern = glob or self.DEFAULT_GLOB
        files = self.recursive_glob(Path(raw_dir), (pattern,))
        if not files:
            raise FileNotFoundError(
                f"cic_iomt2024 loader: no files matching {pattern!r} "
                f"under {raw_dir}"
            )

        parts: list[pd.DataFrame] = []
        for f in files:
            df = self.read_csv_with_encoding_fallback(f)
            df = df.rename(columns={c: c.strip() for c in df.columns})
            # Skip empty / malformed shards.
            if df.empty:
                continue
            df[label_col] = _label_from_filename(f.stem)
            parts.append(df)

        if not parts:
            raise RuntimeError(
                f"cic_iomt2024 loader: every CSV under {raw_dir} was empty"
            )

        df = pd.concat(parts, ignore_index=True, sort=False)
        return df, label_col
