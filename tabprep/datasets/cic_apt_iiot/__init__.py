"""CIC-APT-IIoT-2024 dataset package — UNB CIC's APT-in-IIoT release.

Importing this package registers `CICAPTIIoTLoader`
(`@loader("cic_apt_iiot")`) and `CICAPTIIoTDownloader`
(`@downloader("cic_apt_iiot")`).
"""
from tabprep.datasets.cic_apt_iiot.downloader import CICAPTIIoTDownloader  # noqa: F401
from tabprep.datasets.cic_apt_iiot.loader import CICAPTIIoTLoader  # noqa: F401
