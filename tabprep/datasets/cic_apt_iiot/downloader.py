"""CIC-APT-IIoT-2024 downloader: UNB CIC mirror + licence-consent form.

UNB CIC distributes its 2024 Industrial-IoT APT dataset behind a
licence-consent form (Google Forms). Once consented, the bundled ZIP
is fetched from the public `cicresearch.ca` mirror.

The licence form is informational — UNB CIC tracks submissions for
grant-reporting / bibliometric purposes but doesn't gate the URL on a
session cookie. We auto-submit it with the user's TABPREP_USER_*
identity (or placeholder defaults with a warning), then fetch the ZIP.

Set `TABPREP_USER_NAME`, `TABPREP_USER_EMAIL`, `TABPREP_USER_AFFILIATION`,
and `TABPREP_USER_PURPOSE` env vars to identify yourself properly. CIC
uses these for grant-reporting — submitting placeholder data is rude.
"""
from __future__ import annotations

from typing import ClassVar

from tabprep.datasets._base import HTTPArchiveDownloader, downloader


@downloader("cic_apt_iiot")
class CICAPTIIoTDownloader(HTTPArchiveDownloader):
    url: ClassVar[str] = (
        "http://cicresearch.ca/IOTDataset/CIC-APT-IIoT-2024/Dataset/"
        "CIC-APT-IIoT-2024.zip"
    )
    archive_format: ClassVar[str] = "zip"
    landing_url: ClassVar[str] = (
        "https://www.unb.ca/cic/datasets/cic-apt-iiot-2024.html"
    )
    licence_note: ClassVar[str] = (
        "CC-BY 4.0 — please cite the UNB CIC release paper."
    )

    # CIC's request form on Google Forms. The form ID rotates over
    # time; users hitting a 404 should check the landing page above
    # for the current URL and override via a subclass.
    consent_form_url: ClassVar[str] = (
        "https://docs.google.com/forms/d/e/cic-apt-iiot-2024-request/formResponse"
    )
    consent_form_fields: ClassVar[dict[str, str]] = {
        "dataset": "CIC-APT-IIoT-2024",
        "licence_accepted": "true",
    }
