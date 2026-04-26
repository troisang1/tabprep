"""`BaseDownloader` — abstract base for dataset downloaders.

A downloader fetches the raw bytes for a dataset into a local
`cached_at` directory. Concrete subclasses live under
`tabprep/datasets/<name>/downloader.py` and register themselves with
`@downloader("name")`.

The base class provides:

  * `download(dest_dir)` — abstract, must be overridden;
  * `is_cache_populated(dest_dir)` — default idempotency check (any
    non-empty file under `dest_dir`); override if your dataset has a
    more specific completeness criterion (e.g. presence of a sentinel
    `_complete` marker file);
  * `refusal_message()` — human-readable explanation for form-gated
    datasets that we do **not** auto-download (CIC, IEEE DataPort,
    UNSW SharePoint, Mendeley JS-presigned). Used by the CLI to
    surface a friendly hint when `download()` is called on a profile
    whose `is_supported = False`.

Three well-known concrete subclasses live in the framework:
  * `HTTPArchiveDownloader` — generic single-URL fetch + extract
    (tar.gz / zip / gz / single file). Used by IoT-23, UCI archive, etc.
  * `HTTPMultiURLDownloader` — multi-URL variant (e.g. UNSW-NB15's
    four numbered CSVs on Zenodo).
  * `FormGatedDownloader` — polite refusal that prints `landing_url`
    for the user to visit. Used for upstreams where the download URL
    is genuinely behind interactive auth (Mendeley JS-signed, etc.).

Both `HTTPArchiveDownloader` and `HTTPMultiURLDownloader` honour
**licence-consent forms**: subclasses can set `consent_form_url` (and
optionally `consent_form_fields` / `consent_form_user_keys`) to
auto-POST a licence-acceptance form before fetching. User identity is
read from `TABPREP_USER_NAME`/`EMAIL`/`AFFILIATION`/`PURPOSE` env vars,
falling back to clearly-labelled placeholders with a loud warning.
This serves UNB CIC's licence-consent forms, UNSW Bot-IoT's terms-of-
use, and similar honor-system click-throughs. Strictly-gated datasets
(JS-signed S3, SharePoint with auth) still need `FormGatedDownloader`.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from tabprep.core.downloader import (
    _has_data,
    download_and_extract,
    derive_target_name,
)


# ---------------------------------------------------------------------------
# Licence-consent helpers (used by HTTPArchiveDownloader + HTTPMultiURLDownloader)
# ---------------------------------------------------------------------------

DEFAULT_USER_INFO: dict[str, str] = {
    "name":        "tabprep User",
    "email":       "tabprep-user@example.invalid",
    "affiliation": "tabprep automated download",
    "purpose":     "Reproducible ML benchmark preparation",
}
"""Placeholder identity used for licence-consent forms when the user
hasn't set the corresponding `TABPREP_USER_*` env vars. Deliberately
clear that this is a placeholder — dataset providers can see the
request comes from this tool, not a fake real-looking name. Users
**should** override these via env vars before running form-gated
profiles in production."""


def _get_user_info() -> dict[str, str]:
    """Read user identity from `TABPREP_USER_NAME`/`EMAIL`/`AFFILIATION`/
    `PURPOSE` env vars, falling back to `DEFAULT_USER_INFO` placeholders.

    Prints a one-line warning per unset key so the user sees clearly
    what placeholder values are being submitted. Many dataset providers
    (UNB CIC, UNSW Bot-IoT) record these submissions for grant-reporting
    or bibliometric purposes — please set your real info before running
    a consent-form profile in published work.
    """
    info = dict(DEFAULT_USER_INFO)
    using_defaults: list[str] = []
    for key in info:
        env_key = f"TABPREP_USER_{key.upper()}"
        val = os.environ.get(env_key)
        if val:
            info[key] = val
        else:
            using_defaults.append(key)
    if using_defaults:
        keys = ", ".join(using_defaults)
        env_names = ", ".join(f"TABPREP_USER_{k.upper()}" for k in using_defaults)
        print(f"[tabprep] WARNING: licence consent will use placeholder "
              f"values for: {keys}")
        print(f"[tabprep]          set {env_names} to override "
              f"(see datasets/<name>/README.md).")
    return info


def _submit_consent_form(
    form_url: str,
    *,
    extra_fields: dict[str, str] | None = None,
    user_keys: tuple[str, ...] = ("name", "email", "affiliation", "purpose"),
) -> None:
    """POST a licence-consent form. Best-effort: failures are logged
    but don't abort — many providers' download URLs work even when
    the form-submission endpoint changes / 404s, since the form is
    informational rather than auth-gating.

    Subclasses provide `extra_fields` for static form values (licence
    acceptance checkboxes, dataset name, etc.). The `user_keys` tuple
    selects which identity fields from `_get_user_info()` to include.
    """
    if not form_url:
        return
    info = _get_user_info()
    payload: dict[str, str] = dict(extra_fields or {})
    for k in user_keys:
        if k in info:
            payload[k] = info[k]

    print(f"[tabprep] submitting consent form to {form_url}")
    for k, v in payload.items():
        # Truncate long values in the log for readability.
        v_display = v if len(v) <= 60 else (v[:57] + "...")
        print(f"          {k}: {v_display}")
    try:
        import requests
        response = requests.post(form_url, data=payload, timeout=30)
        # 200/302 are typical successes; 4xx/5xx warn but don't abort.
        if response.status_code >= 400:
            print(f"[tabprep] consent form returned HTTP {response.status_code} "
                  f"— proceeding anyway (form is informational).")
        else:
            print(f"[tabprep] consent submitted (HTTP {response.status_code})")
    except Exception as exc:                                          # noqa: BLE001
        print(f"[tabprep] consent form submission failed: {exc}")
        print("[tabprep]   continuing — most providers gate on a separate "
              "download URL, not on the form submission itself.")


class BaseDownloader(ABC):
    """Abstract base. Subclasses implement `download(dest_dir)`."""

    # --- class-level metadata that subclasses set -------------------------

    is_supported: ClassVar[bool] = True
    """Whether this downloader can actually fetch bytes. False marks a
    polite-refusal subclass for form-gated upstreams (CIC, etc.)."""

    landing_url: ClassVar[str] = ""
    """Human-facing landing page where the licence form lives. Surfaced
    in the refusal message for form-gated downloaders."""

    licence_note: ClassVar[str] = ""
    """One-line summary of the dataset's licence (e.g. "CC-BY 4.0",
    "Research use only — UNSW academic licence"). Optional."""

    # --- the contract ----------------------------------------------------

    @abstractmethod
    def download(self, dest_dir: Path) -> None:
        """Fetch raw data into `dest_dir`. Idempotent: skip if data
        already present, raise if a precondition fails (network down,
        upstream URL changed, checksum mismatch).
        """
        ...

    # --- shared helpers --------------------------------------------------

    def is_cache_populated(self, dest_dir: Path) -> bool:
        """Default: any non-empty file under `dest_dir` is a cache hit.

        Override this if your dataset has a more specific completeness
        criterion (e.g. presence of all expected sub-directories).
        """
        return _has_data(Path(dest_dir))

    def refusal_message(self) -> str:
        """Surface this when the user calls a form-gated downloader."""
        url = self.landing_url or "<see profile description>"
        return (
            f"This dataset cannot be auto-downloaded "
            f"({self.licence_note or 'upstream is form/JS-gated'}).\n"
            f"  Visit:  {url}\n"
            f"  Complete the licence form, then place the raw data under "
            f"the profile's `cached_at:` path and re-run `tabprep prepare`."
        )


# ---------------------------------------------------------------------------
# Concrete convenience subclasses
# ---------------------------------------------------------------------------

class HTTPArchiveDownloader(BaseDownloader):
    """Generic single-URL fetch + (optional) archive extract.

    Subclasses set the class attributes:

        url: str                          # required
        sha256: str | None                # optional integrity check
        archive_format: str | None        # tar.gz | tgz | tar | zip | gz | none
                                          # None → auto-detect from URL suffix
        consent_form_url: str             # optional — POST a licence-consent
                                          #   form before fetching
        consent_form_fields: dict[str, str]
                                          # static fields the form expects
                                          # (e.g. {"licence_accepted": "true",
                                          #         "dataset": "CIC-APT-IIoT-2024"})
        consent_form_user_keys: tuple[str, ...]
                                          # subset of (name, email,
                                          # affiliation, purpose) to include

    Useful for IoT-23, UCI archive, Zenodo direct downloads, and
    UNB CIC datasets whose download URL is gated by a click-through
    licence consent form.
    """

    url: ClassVar[str] = ""
    sha256: ClassVar[str | None] = None
    archive_format: ClassVar[str | None] = None
    consent_form_url: ClassVar[str] = ""
    consent_form_fields: ClassVar[dict[str, str]] = {}
    consent_form_user_keys: ClassVar[tuple[str, ...]] = (
        "name", "email", "affiliation", "purpose",
    )

    def download(self, dest_dir: Path) -> None:
        if not self.url:
            raise RuntimeError(
                f"{type(self).__name__}: subclass must set `url` class attribute"
            )
        # Cache-hit short-circuit BEFORE the consent form. download_and_extract
        # also performs this check internally, but only after a consent_form
        # POST has already happened — which would re-submit a licence form
        # to the upstream provider on every prepare call. Bail at the top.
        dest = Path(dest_dir)
        if self.is_cache_populated(dest):
            print(f"[tabprep] cache hit: {dest} already populated, skipping download")
            return
        if self.consent_form_url:
            _submit_consent_form(
                self.consent_form_url,
                extra_fields=self.consent_form_fields,
                user_keys=self.consent_form_user_keys,
            )
        download_and_extract(
            self.url,
            dest,
            archive_format=self.archive_format,
            expected_sha256=self.sha256,
        )


class HTTPMultiURLDownloader(BaseDownloader):
    """Multi-URL variant for datasets that ship as several stand-alone
    files at distinct URLs (e.g. UNSW-NB15's four numbered CSVs on
    Zenodo, NSL-KDD's separate train/test files).

    Subclasses set:

        urls: tuple[str, ...]                  # required, fetched in order
        archive_format: str | None             # applied uniformly to every URL
        consent_form_url: str                  # optional — POST consent first
        consent_form_fields: dict[str, str]    # static fields
        consent_form_user_keys: tuple[str, ...]  # which user_info keys to send

    The consent form is submitted **once** before any URL is fetched.
    """

    urls: ClassVar[tuple[str, ...]] = ()
    archive_format: ClassVar[str | None] = None
    consent_form_url: ClassVar[str] = ""
    consent_form_fields: ClassVar[dict[str, str]] = {}
    consent_form_user_keys: ClassVar[tuple[str, ...]] = (
        "name", "email", "affiliation", "purpose",
    )

    def download(self, dest_dir: Path) -> None:
        if not self.urls:
            raise RuntimeError(
                f"{type(self).__name__}: subclass must set `urls` class attribute"
            )
        cached = Path(dest_dir)
        # Cache-hit short-circuit BEFORE the consent form. We consider
        # the cache fully populated only when EVERY expected target file
        # is present and non-empty — partial caches still trigger a fetch
        # for the missing files (download_and_extract's per-file check
        # then short-circuits the present ones).
        targets = [derive_target_name(u) for u in self.urls]
        if all(
            (cached / t).is_file() and (cached / t).stat().st_size > 0
            for t in targets
        ):
            print(f"[tabprep] cache hit: {cached} all {len(targets)} target files present, skipping download")
            return
        if self.consent_form_url:
            _submit_consent_form(
                self.consent_form_url,
                extra_fields=self.consent_form_fields,
                user_keys=self.consent_form_user_keys,
            )
        for u, target in zip(self.urls, targets):
            download_and_extract(
                u,
                cached,
                archive_format=self.archive_format,
                target_name=target,
            )


class FormGatedDownloader(BaseDownloader):
    """Polite-refusal downloader for upstreams that gate access behind
    a licence form, JS-signed S3 URLs, or interactive auth.

    Subclasses just set `landing_url` and `licence_note`. Calling
    `download()` raises with a clear hint for the user.
    """

    is_supported: ClassVar[bool] = False

    def download(self, dest_dir: Path) -> None:
        raise RuntimeError(self.refusal_message())
