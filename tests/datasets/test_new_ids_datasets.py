"""Smoke tests for the four added IDS dataset packages: nsl_kdd,
cic_apt_iiot, insdn, bot_iot.

Each test checks registration, class-attribute pinning, and basic
loader behaviour on a tiny synthetic CSV. The downloader's actual
network call is exercised elsewhere — these tests stay offline.
"""
from __future__ import annotations

import pytest

from tabprep.datasets import DOWNLOADER_REGISTRY, LOADER_REGISTRY
from tabprep.datasets.bot_iot import BotIoTDownloader, BotIoTLoader
from tabprep.datasets.cic_apt_iiot import (
    CICAPTIIoTDownloader,
    CICAPTIIoTLoader,
)
from tabprep.datasets.insdn import InSDNDownloader, InSDNLoader
from tabprep.datasets.nsl_kdd import NSLKDDDownloader, NSLKDDLoader


# ---------- registration ---------------------------------------------------

@pytest.mark.parametrize("name,loader_cls,downloader_cls", [
    ("nsl_kdd",      NSLKDDLoader,      NSLKDDDownloader),
    ("cic_apt_iiot", CICAPTIIoTLoader,  CICAPTIIoTDownloader),
    ("insdn",        InSDNLoader,       InSDNDownloader),
    ("bot_iot",      BotIoTLoader,      BotIoTDownloader),
])
def test_registered(name, loader_cls, downloader_cls):
    assert LOADER_REGISTRY[name] is loader_cls
    assert DOWNLOADER_REGISTRY[name] is downloader_cls


# ---------- nsl_kdd downloader pin ----------------------------------------

def test_nsl_kdd_downloader_metadata():
    assert NSLKDDDownloader.url.endswith(".zip")
    assert "NSL-KDD" in NSLKDDDownloader.url
    assert NSLKDDDownloader.archive_format == "zip"
    assert "unb.ca" in NSLKDDDownloader.landing_url
    # No consent form for NSL-KDD (open access).
    assert NSLKDDDownloader.consent_form_url == ""


# ---------- cic_apt_iiot downloader pin -----------------------------------

def test_cic_apt_iiot_downloader_metadata():
    assert CICAPTIIoTDownloader.archive_format == "zip"
    assert "CIC-APT-IIoT-2024" in CICAPTIIoTDownloader.url
    # Has a consent form.
    assert CICAPTIIoTDownloader.consent_form_url != ""
    assert CICAPTIIoTDownloader.consent_form_fields["dataset"] == "CIC-APT-IIoT-2024"


# ---------- insdn / bot_iot consent attrs ---------------------------------

def test_insdn_has_consent_form():
    assert InSDNDownloader.consent_form_url != ""
    assert InSDNDownloader.licence_note.startswith("CC-BY")
    assert len(InSDNDownloader.urls) >= 1


def test_bot_iot_has_consent_form():
    assert BotIoTDownloader.consent_form_url != ""
    assert "UNSW" in BotIoTDownloader.licence_note or \
           "Koroniotis" in BotIoTDownloader.licence_note
    assert "UNSW" in BotIoTDownloader.consent_form_url or \
           "research.unsw" in BotIoTDownloader.consent_form_url


# ---------- nsl_kdd loader: synthetic KDDTrain+/Test+ ---------------------

# NSL-KDD's TXT is comma-separated, no header, with 41 features +
# trailing `label` and `difficulty`.
_NSL_KDD_LINE_BENIGN = (
    "0,tcp,http,SF,491,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,2,2,"
    "0.00,0.00,0.00,0.00,1.00,0.00,0.00,150,25,0.17,0.03,0.17,"
    "0.00,0.00,0.00,0.05,0.00,normal,20"
)
_NSL_KDD_LINE_DOS = (
    "0,udp,private,SF,105,146,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,"
    "0.00,0.00,0.00,0.00,1.00,0.00,0.00,254,254,1.00,0.01,0.00,"
    "0.00,0.00,0.00,0.00,0.00,neptune,15"
)


def test_nsl_kdd_loader_parses_two_files(tmp_path):
    train = tmp_path / "KDDTrain+.txt"
    test = tmp_path / "KDDTest+.txt"
    train.write_text(_NSL_KDD_LINE_BENIGN + "\n" + _NSL_KDD_LINE_DOS + "\n")
    test.write_text(_NSL_KDD_LINE_BENIGN + "\n")

    df, label = NSLKDDLoader().load(tmp_path, "label")
    assert label == "label"
    assert len(df) == 3
    assert "label" in df.columns
    # `difficulty` dropped by default.
    assert "difficulty" not in df.columns
    assert df["label"].tolist() == ["normal", "neptune", "normal"]


def test_nsl_kdd_loader_keeps_difficulty_when_opted_in(tmp_path):
    p = tmp_path / "KDDTrain+.txt"
    p.write_text(_NSL_KDD_LINE_BENIGN + "\n")
    df, _ = NSLKDDLoader().load(
        tmp_path, "label",
        use_files=["KDDTrain+.txt"],
        drop_difficulty=False,
    )
    assert "difficulty" in df.columns


def test_nsl_kdd_loader_raises_when_use_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="KDDTrain"):
        NSLKDDLoader().load(tmp_path, "label", use_files=["KDDTrain+.txt"])


# ---------- shared concat-csv loaders -------------------------------------

@pytest.mark.parametrize("loader_cls", [
    CICAPTIIoTLoader,
    InSDNLoader,
    BotIoTLoader,
])
def test_concat_csv_loader_strips_whitespace_in_column_names(tmp_path, loader_cls):
    """The CIC family ships CSVs with leading whitespace in column
    names (' Label', ' Flow ID'). Each loader must strip these."""
    p = tmp_path / "x.csv"
    p.write_text(" feat , Label \n1.0,benign\n2.0,attack\n")
    df, label_col = loader_cls().load(tmp_path, "label")
    assert label_col == "label"
    assert "feat" in df.columns
    assert "Label" in df.columns


@pytest.mark.parametrize("loader_cls", [
    CICAPTIIoTLoader, InSDNLoader, BotIoTLoader,
])
def test_concat_csv_loader_raises_when_empty(tmp_path, loader_cls):
    with pytest.raises(FileNotFoundError, match="no files matching"):
        loader_cls().load(tmp_path, "label")


@pytest.mark.parametrize("loader_cls", [
    CICAPTIIoTLoader, InSDNLoader, BotIoTLoader,
])
def test_concat_csv_loader_concatenates_multiple_files(tmp_path, loader_cls):
    (tmp_path / "a.csv").write_text("feat,Label\n1.0,benign\n2.0,attack\n")
    (tmp_path / "b.csv").write_text("feat,Label\n3.0,benign\n")
    df, _ = loader_cls().load(tmp_path, "label")
    assert len(df) == 3
