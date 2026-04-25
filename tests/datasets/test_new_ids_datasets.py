"""Smoke tests for the four added IDS dataset packages: nsl_kdd,
cic_apt_iiot, insdn, bot_iot.

Each test checks registration, class-attribute pinning, and basic
loader behaviour on a tiny synthetic CSV. The downloader's actual
network call is exercised elsewhere — these tests stay offline.
"""
from __future__ import annotations

import pandas as pd
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

def test_nsl_kdd_downloader_uses_github_mirror():
    """UNB CIC's IP-based mirror redirects everything to a landing
    index in 2025+, so we use the well-maintained GitHub mirror at
    `defcom17/NSL_KDD` for the canonical .txt files."""
    # HTTPMultiURLDownloader, four URLs (Train+ / Train+_20Percent / Test+ / Test-21).
    assert len(NSLKDDDownloader.urls) == 4
    for u in NSLKDDDownloader.urls:
        assert "raw.githubusercontent.com" in u
        assert "defcom17/NSL_KDD" in u
        assert u.endswith(".txt")


# ---------- cic_apt_iiot downloader pin -----------------------------------

def test_cic_apt_iiot_downloader_is_form_gated():
    """UNB CIC's 2025 restructuring took the IP-based mirror offline;
    the dataset is now distributed via a per-request form. We mark the
    downloader is_supported=False and refuse rather than try to scrape."""
    assert CICAPTIIoTDownloader.is_supported is False
    assert "iiot-dataset-2024" in CICAPTIIoTDownloader.landing_url
    assert "request form" in CICAPTIIoTDownloader.licence_note.lower()


# ---------- insdn downloader pin ------------------------------------------

def test_insdn_downloader_uses_kaggle_mirror():
    """Mendeley's per-file URLs are JS-rendered (rotate per session),
    but the Kaggle public mirror `badcodebuilder/insdn-dataset` carries
    the same 3 CSVs and is auto-fetchable via Kaggle's
    `/api/v1/datasets/download/` endpoint (no auth for CC-BY datasets)."""
    assert InSDNDownloader.is_supported is True
    assert "kaggle.com" in InSDNDownloader.url
    assert "insdn-dataset" in InSDNDownloader.url
    assert InSDNDownloader.archive_format == "zip"
    assert "mendeley.com" in InSDNDownloader.landing_url
    assert InSDNDownloader.licence_note.startswith("CC-BY")


# ---------- bot_iot downloader pin (OpenML mirror) ------------------------

def test_bot_iot_downloader_uses_openml_mirror():
    """AARNet's Cloudstor host where UNSW originally distributed Bot-IoT
    was decommissioned in 2023. We use the OpenML mirror (id 42072,
    `bot-iot-all-features`) — the 10-best-features subset, no consent
    form, scriptable."""
    assert BotIoTDownloader.is_supported is True
    assert BotIoTDownloader.OPENML_NAME == "bot-iot-all-features"
    assert BotIoTDownloader.OPENML_VERSION == 1
    assert "research.unsw.edu.au" in BotIoTDownloader.landing_url
    assert "OpenML" in BotIoTDownloader.licence_note


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


@pytest.mark.parametrize("loader_cls", [CICAPTIIoTLoader, InSDNLoader])
def test_concat_csv_loader_raises_when_empty(tmp_path, loader_cls):
    with pytest.raises(FileNotFoundError, match="no files matching"):
        loader_cls().load(tmp_path, "label")


@pytest.mark.parametrize("loader_cls", [CICAPTIIoTLoader, InSDNLoader])
def test_concat_csv_loader_concatenates_multiple_files(tmp_path, loader_cls):
    (tmp_path / "a.csv").write_text("feat,Label\n1.0,benign\n2.0,attack\n")
    (tmp_path / "b.csv").write_text("feat,Label\n3.0,benign\n")
    df, _ = loader_cls().load(tmp_path, "label")
    assert len(df) == 3


# ---------- bot_iot loader: mocked sklearn fetch_openml -------------------

def test_bot_iot_loader_uses_openml(monkeypatch):
    """BotIoTLoader fetches via sklearn.fetch_openml under the hood."""
    import sys
    import types

    feats = pd.DataFrame({"f0": [0.1, 0.2], "f1": [3.0, 4.0]})
    target = pd.Series(["DDoS", "Normal"])
    bunch = types.SimpleNamespace(data=feats.copy(), target=target.copy())
    last_call: dict = {}

    def fake_fetch(name, version=1, as_frame=True, parser="auto"):
        last_call["name"] = name
        last_call["version"] = version
        return bunch

    sk_datasets = sys.modules.setdefault(
        "sklearn.datasets", types.ModuleType("sklearn.datasets")
    )
    monkeypatch.setattr(sk_datasets, "fetch_openml", fake_fetch, raising=False)

    df, label = BotIoTLoader().load("/tmp/_unused", "label")
    assert label == "label"
    assert "label" in df.columns
    assert df["label"].tolist() == ["DDoS", "Normal"]
    assert last_call["name"] == "bot-iot-all-features"
    assert last_call["version"] == 1
