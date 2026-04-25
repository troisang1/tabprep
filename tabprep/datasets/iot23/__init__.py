"""IoT-23 dataset package — Stratosphere Lab CTU malware captures.

Importing this package registers `IoT23Loader` (`@loader("iot23")`) and
`IoT23Downloader` (`@downloader("iot23")`) with the framework
registries. The profile at `profiles/iot23.yaml` references both by
short name.
"""
from tabprep.datasets.iot23.downloader import IoT23Downloader  # noqa: F401
from tabprep.datasets.iot23.loader import IoT23Loader  # noqa: F401
