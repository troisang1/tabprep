"""Bot-IoT downloader: OpenML mirror via sklearn.fetch_openml.

Bot-IoT (Koroniotis, Moustafa, Sitnikova, Turnbull, 2018) is one of
the most cited IoT NIDS datasets. UNSW originally distributed it via
AARNet Cloudstor, but that service was decommissioned in 2023 and the
host (`cloudstor.aarnet.edu.au`) no longer resolves.

The dataset is mirrored on OpenML as id 42072 (`bot-iot-all-features`),
which is what this downloader uses. The OpenML mirror is the
"10-best-features" subset (3.6M rows × 10 numeric features + label)
— the same subset most Bot-IoT papers use, small enough to auto-fetch
without a consent form.

For the full ~16.7 GB pcap+argus+csv distribution, the user should
visit the UNSW landing page and request access via the Microsoft
Forms application; that path is not auto-fetchable.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from tabprep.datasets._base import BaseDownloader, downloader


@downloader("bot_iot")
class BotIoTDownloader(BaseDownloader):
    """Pre-fetch the Bot-IoT 10-best-features subset via the OpenML mirror.

    Profile usage:
        downloader: bot_iot
        cached_at: raw/bot_iot/

    Internally calls `sklearn.datasets.fetch_openml('bot-iot-all-features',
    version=1)` which caches under `~/scikit_learn_data/`. Writes a
    `_complete` marker into `cached_at/` after a successful fetch so
    re-runs short-circuit.
    """

    is_supported: ClassVar[bool] = True
    landing_url: ClassVar[str] = (
        "https://research.unsw.edu.au/projects/bot-iot-dataset"
    )
    licence_note: ClassVar[str] = (
        "Research-use only — UNSW academic licence (mirrored as OpenML "
        "id 42072); please cite Koroniotis et al. (2018)."
    )

    OPENML_NAME: ClassVar[str] = "bot-iot-all-features"
    OPENML_VERSION: ClassVar[int] = 1
    SENTINEL: ClassVar[str] = "_complete"

    def download(self, dest_dir: Path) -> None:
        dest = Path(dest_dir)
        marker = dest / self.SENTINEL
        if marker.is_file():
            return  # cache hit — sklearn already has the bytes

        from sklearn.datasets import fetch_openml

        # Network call — populates ~/scikit_learn_data/.
        fetch_openml(
            self.OPENML_NAME, version=self.OPENML_VERSION,
            as_frame=True, parser="auto",
        )
        dest.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"openml:{self.OPENML_NAME}\n", encoding="utf-8")
