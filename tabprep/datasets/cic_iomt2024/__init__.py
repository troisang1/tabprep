"""CIC-IoMT-2024 dataset package — UNB CIC's 2024 IoMT release.

The Kaggle public mirror ships per-pcap CSVs under `csv/test/` and
`csv/train/`, with the label encoded in the filename (e.g.,
`ARP_Spoofing_test.pcap.csv` → label "ARP_Spoofing"). This package
walks those directories, derives the label per-file, and concatenates.

Importing this package registers `CICIoMT2024Loader`
(`@loader("cic_iomt2024")`) and `CICIoMT2024Downloader`
(`@downloader("cic_iomt2024")`).
"""
from tabprep.datasets.cic_iomt2024.downloader import CICIoMT2024Downloader  # noqa: F401
from tabprep.datasets.cic_iomt2024.loader import CICIoMT2024Loader  # noqa: F401
