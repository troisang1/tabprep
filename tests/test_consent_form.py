"""Unit tests for the licence-consent-form helpers in
`tabprep/datasets/_base/downloader.py`.

The HTTP POST is mocked via monkeypatching `requests.post` so the
tests stay offline. Tests cover:

  * `_get_user_info` env-var override + placeholder fallback (with
    warning emitted to stdout).
  * `_submit_consent_form` payload construction.
  * `_submit_consent_form` failure modes (network exception, 4xx
    response) — both should warn but not abort.
"""
from __future__ import annotations


from tabprep.datasets._base.downloader import (
    DEFAULT_USER_INFO,
    _get_user_info,
    _submit_consent_form,
)


# ---------- _get_user_info -----------------------------------------------

def test_get_user_info_returns_placeholders_when_env_unset(monkeypatch, capsys):
    for k in DEFAULT_USER_INFO:
        monkeypatch.delenv(f"TABPREP_USER_{k.upper()}", raising=False)
    info = _get_user_info()
    assert info == DEFAULT_USER_INFO
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "placeholder" in captured.out


def test_get_user_info_overrides_from_env(monkeypatch, capsys):
    monkeypatch.setenv("TABPREP_USER_NAME", "Real Name")
    monkeypatch.setenv("TABPREP_USER_EMAIL", "real@example.edu")
    monkeypatch.setenv("TABPREP_USER_AFFILIATION", "Real Lab")
    monkeypatch.setenv("TABPREP_USER_PURPOSE", "Real research")

    info = _get_user_info()
    assert info["name"] == "Real Name"
    assert info["email"] == "real@example.edu"
    assert info["affiliation"] == "Real Lab"
    assert info["purpose"] == "Real research"
    # No warning since all fields supplied.
    captured = capsys.readouterr()
    assert "WARNING" not in captured.out


def test_get_user_info_partial_override_warns_about_missing_only(monkeypatch, capsys):
    monkeypatch.setenv("TABPREP_USER_NAME", "Half Real")
    monkeypatch.delenv("TABPREP_USER_EMAIL", raising=False)
    monkeypatch.delenv("TABPREP_USER_AFFILIATION", raising=False)
    monkeypatch.delenv("TABPREP_USER_PURPOSE", raising=False)

    info = _get_user_info()
    assert info["name"] == "Half Real"
    assert info["email"] == DEFAULT_USER_INFO["email"]
    captured = capsys.readouterr()
    assert "email" in captured.out
    assert "TABPREP_USER_EMAIL" in captured.out
    # Name was supplied — should not appear in the placeholder list.
    assert "name," not in captured.out.lower()  # 'name' alone may appear in prose


# ---------- _submit_consent_form -----------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


def test_submit_consent_form_no_url_is_noop(monkeypatch):
    """An empty form_url short-circuits before any HTTP call."""
    called = {"posted": False}

    def fake_post(*args, **kwargs):
        called["posted"] = True
        return _FakeResponse(200)

    # Patch even though it shouldn't be called — to prove it isn't.
    import requests
    monkeypatch.setattr(requests, "post", fake_post, raising=False)
    _submit_consent_form("")
    assert called["posted"] is False


def test_submit_consent_form_posts_correct_payload(monkeypatch, capsys):
    captured_args: dict = {}

    def fake_post(url, data=None, timeout=None):
        captured_args["url"] = url
        captured_args["data"] = data
        return _FakeResponse(200)

    monkeypatch.setenv("TABPREP_USER_NAME", "Tester")
    monkeypatch.setenv("TABPREP_USER_EMAIL", "test@example.edu")
    monkeypatch.setenv("TABPREP_USER_AFFILIATION", "Lab")
    monkeypatch.setenv("TABPREP_USER_PURPOSE", "test")

    import requests
    monkeypatch.setattr(requests, "post", fake_post, raising=False)
    _submit_consent_form(
        "https://example.com/consent",
        extra_fields={"dataset": "X", "licence_accepted": "true"},
        user_keys=("name", "email"),
    )

    assert captured_args["url"] == "https://example.com/consent"
    assert captured_args["data"]["dataset"] == "X"
    assert captured_args["data"]["licence_accepted"] == "true"
    assert captured_args["data"]["name"] == "Tester"
    assert captured_args["data"]["email"] == "test@example.edu"
    # `affiliation` and `purpose` excluded since user_keys=("name","email").
    assert "affiliation" not in captured_args["data"]
    assert "purpose" not in captured_args["data"]


def test_submit_consent_form_4xx_response_does_not_abort(monkeypatch, capsys):
    """A 404/500 from the consent endpoint is logged but doesn't raise —
    most providers' download URLs are independent of form submission."""
    monkeypatch.setenv("TABPREP_USER_NAME", "Tester")

    def fake_post(*args, **kwargs):
        return _FakeResponse(404)

    import requests
    monkeypatch.setattr(requests, "post", fake_post, raising=False)
    # Should NOT raise.
    _submit_consent_form("https://example.com/consent")
    captured = capsys.readouterr()
    assert "404" in captured.out


def test_submit_consent_form_network_exception_does_not_abort(monkeypatch, capsys):
    """A connection error is logged but doesn't abort the download."""
    monkeypatch.setenv("TABPREP_USER_NAME", "Tester")

    def fake_post(*args, **kwargs):
        raise ConnectionError("network unreachable")

    import requests
    monkeypatch.setattr(requests, "post", fake_post, raising=False)
    # Should NOT raise.
    _submit_consent_form("https://example.com/consent")
    captured = capsys.readouterr()
    assert "failed" in captured.out
    assert "continuing" in captured.out


# ---------- HTTPArchiveDownloader integration -----------------------------

def test_http_archive_downloader_submits_consent_before_download(
    monkeypatch, tmp_path,
):
    """When `consent_form_url` is set, HTTPArchiveDownloader.download
    must POST the consent form *before* invoking the underlying
    download_and_extract.

    Note: `tabprep.datasets._base.downloader` is shadowed by the
    re-exported `downloader` decorator from `_registry`, so we resolve
    the module via sys.modules rather than direct attribute access.
    """
    import sys
    from tabprep.datasets._base.downloader import HTTPArchiveDownloader

    call_order: list[str] = []

    def fake_post(url, data=None, timeout=None):
        call_order.append("consent")
        return _FakeResponse(200)

    def fake_download_and_extract(url, dest, **kwargs):
        call_order.append(f"download:{url}")

    import requests
    dl_mod = sys.modules["tabprep.datasets._base.downloader"]
    monkeypatch.setattr(requests, "post", fake_post, raising=False)
    monkeypatch.setattr(dl_mod, "download_and_extract", fake_download_and_extract)
    monkeypatch.setenv("TABPREP_USER_NAME", "Tester")

    class _ConsentTestDL(HTTPArchiveDownloader):
        url = "https://example.com/data.zip"
        archive_format = "zip"
        consent_form_url = "https://example.com/consent"
        consent_form_fields = {"licence_accepted": "true"}

    _ConsentTestDL().download(tmp_path)
    assert call_order == ["consent", "download:https://example.com/data.zip"]
