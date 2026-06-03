"""Cleaning ops: drop columns, NaN/Inf handling, IP/MAC-leakage removal."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from tabprep.ops._registry import op


@op("drop_columns")
def drop_columns(df: pd.DataFrame, *, label_col: str,
                 columns: list[str]) -> pd.DataFrame:
    """Drop the named columns, ignoring any that are absent."""
    return df.drop(columns=[c for c in (columns or []) if c in df.columns], errors="ignore")


@op("drop_constant_columns")
def drop_constant_columns(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Drop columns with a single unique non-NaN value (excluding the label)."""
    drop = []
    for c in df.columns:
        if c == label_col:
            continue
        if df[c].nunique(dropna=True) <= 1:
            drop.append(c)
    return df.drop(columns=drop) if drop else df


# IP / host / flow-identity column tokens. Matched against a *normalised*
# column name (lowercased, every run of non-alphanumerics collapsed to a
# single "_") so "Source IP", "id.orig_h", "src-ip" and "saddr" all line
# up. Tokens are chosen specific enough not to clip legitimate aggregate
# features: NSL-KDD `dst_host_count` / `dst_host_same_src_port_rate`
# (no `dst_ip`/`dst_addr` token), UNSW-NB15 `is_sm_ips_ports`, IoT-23
# `orig_ip_bytes` (no `orig_h`), and the bare `ip`/`mac` *protocol-presence*
# flags in the CIC-IoT feature CSVs all survive.
_IP_TOKENS = (
    "src_ip", "dst_ip", "source_ip", "destination_ip", "dest_ip",
    "ip_src", "ip_dst", "ip_source", "ip_dest", "ip_address", "ipaddr",
    "srcip", "dstip", "destip",
    "src_addr", "dst_addr", "source_addr", "dest_addr",
    "srcaddr", "dstaddr", "saddr", "daddr",
    "orig_h", "resp_h",          # Zeek/Bro conn.log: id.orig_h / id.resp_h
    "proto_ipv4",                # Edge-IIoT ARP: arp.{src,dst}.proto_ipv4
)
# MAC / link-layer hardware addresses. The `_mac` / `mac_` boundary keeps
# the bare `MAC` protocol-presence flag (CIC-IoT CSVs) from matching, and
# `hw_mac` (not `hw_`) keeps Edge-IIoT's numeric `arp.hw.size` safe.
_MAC_TOKENS = (
    "src_mac", "dst_mac", "source_mac", "dest_mac",
    "srcmac", "dstmac", "mac_src", "mac_dst",
    "hw_mac", "eth_src", "eth_dst", "eth_addr",
    "macaddr", "mac_address",
)
_IDENTITY_TOKENS = _IP_TOKENS + _MAC_TOKENS
# CICFlowMeter 5-tuple identifier ("srcip-dstip-srcport-dstport-proto").
# Matched on the *whole* normalised name so `flow_idle_time` (which would
# match a `flow_id` substring) is left alone.
_FLOW_ID_NAMES = frozenset({"flow_id", "flowid"})


def _norm_colname(name: str) -> str:
    """Lowercase + collapse non-alphanumeric runs to '_' for matching."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


@op("drop_ip_columns")
def drop_ip_columns(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Drop IP- and MAC-address (and flow-id) columns — identity leakage
    in network IDS data.

    A model that sees a flow's source/destination IP or MAC can memorise
    *which host* attacked instead of learning traffic behaviour: it
    inflates benchmark accuracy and collapses on any other network. The
    CICFlowMeter `Flow ID` (a srcip-dstip-srcport-dstport-proto 5-tuple)
    leaks the same identity and is dropped too.

    Column names are normalised (lowercase, non-alphanumerics → "_")
    before matching against `_IDENTITY_TOKENS`; see those token lists for
    the legitimate features deliberately left untouched. Ports and
    timestamps are intentionally NOT dropped here — handle those with an
    explicit `drop_columns` op where a profile wants them gone.
    """
    drop = []
    for c in df.columns:
        if c == label_col:
            continue
        n = _norm_colname(c)
        if n in _FLOW_ID_NAMES or any(tok in n for tok in _IDENTITY_TOKENS):
            drop.append(c)
    return df.drop(columns=drop) if drop else df


# Wall-clock timestamp column names (absolute capture time → temporal
# leakage: attacks happen in fixed windows, so the clock alone separates
# classes). Matched on the WHOLE normalised name — NOT a substring — so
# the many legitimate *timing features* survive: durations (`dur`,
# `duration`, `flow_duration`, `*_duration`), inter-arrival times
# (`Flow IAT Mean`, `Fwd IAT Tot`), idle/active spans
# (`flow_idle_time`, `flow_active_time`, `Idle Max`, `Active Mean`),
# round-trip times (`TcpRtt`), and `RunTime`. Ports are intentionally
# NOT touched here or in `drop_ip_columns` — they are kept as features.
_TIMESTAMP_NAMES = frozenset({
    "ts", "timestamp", "time", "datetime", "date",
    "stime", "ltime",                         # UNSW-NB15 / Bot-IoT start & last time
    "starttime", "endtime", "start_time", "end_time",
    "frame_time",                             # Edge-IIoT frame.time
    "flow_start", "flow_end",
    "first_seen", "last_seen", "date_first_seen", "date_last_seen",
})


@op("drop_timestamp_columns")
def drop_timestamp_columns(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Drop absolute wall-clock timestamp columns — temporal identity
    leakage in network IDS data.

    A capture-session timestamp (e.g. UNSW-NB15 `Stime`/`Ltime`, CIC
    `Timestamp`, Zeek `ts`) lets a model separate classes by *when* the
    traffic was recorded rather than *what* it looks like — attacks are
    typically captured in dedicated time windows, so the clock alone is a
    near-perfect (and useless) discriminator.

    Matching is on the whole normalised column name against
    `_TIMESTAMP_NAMES`, so elapsed-time / inter-arrival *features*
    (durations, IAT, idle/active spans, RTT) are deliberately kept — only
    absolute timestamps go.
    """
    drop = [c for c in df.columns
            if c != label_col and _norm_colname(c) in _TIMESTAMP_NAMES]
    return df.drop(columns=drop) if drop else df


@op("drop_high_nan_columns")
def drop_high_nan_columns(df: pd.DataFrame, *, label_col: str,
                          threshold: float = 0.8) -> pd.DataFrame:
    """Drop columns where the NaN fraction exceeds `threshold`."""
    feat = df.drop(columns=[label_col], errors="ignore")
    na_frac = feat.isna().mean()
    drop = na_frac[na_frac > float(threshold)].index.tolist()
    return df.drop(columns=drop) if drop else df


@op("replace_inf")
def replace_inf(df: pd.DataFrame, *, label_col: str,
                value: float | None = None) -> pd.DataFrame:
    """Replace ±inf with NaN (default) or with a numeric `value`."""
    if value is None:
        return df.replace([np.inf, -np.inf], np.nan)
    return df.replace([np.inf, -np.inf], float(value))


@op("fill_nan")
def fill_nan(df: pd.DataFrame, *, label_col: str,
             value: float = 0.0) -> pd.DataFrame:
    """Fill NaN with a numeric constant (typical: 0)."""
    return df.fillna(float(value))


@op("coerce_numeric")
def coerce_numeric(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Coerce non-label string columns to numeric (NaN on failure)."""
    out = df.copy()
    for c in out.columns:
        if c == label_col:
            continue
        if out[c].dtype == object:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


@op("drop_constant_prefix_columns")
def drop_constant_prefix_columns(df: pd.DataFrame, *, label_col: str,
                                 prefixes: list[str]) -> pd.DataFrame:
    """Drop columns whose name starts with any of `prefixes` AND that are
    constant (single unique value). Common in IDS feeds like ToN-IoT
    where many ssl_/dns_/http_/weird_ columns are sentinel "-" only.
    """
    if not prefixes:
        return df
    drop = []
    for c in df.columns:
        if c == label_col:
            continue
        if any(c.startswith(p) for p in prefixes) and df[c].nunique(dropna=True) <= 1:
            drop.append(c)
    return df.drop(columns=drop) if drop else df


@op("strip_column_whitespace")
def strip_column_whitespace(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Strip leading/trailing whitespace from column names. Common in
    CICIDS-style CSVs where columns are exported as ' Label', ' Flow ID', etc.
    """
    return df.rename(columns={c: c.strip() for c in df.columns})


@op("rename_columns")
def rename_columns(df: pd.DataFrame, *, label_col: str,
                   mapping: dict[str, str]) -> pd.DataFrame:
    """Rename columns according to an explicit `mapping: {old: new}` dict."""
    return df.rename(columns=mapping or {})


@op("filter_rows_label_isnull")
def filter_rows_label_isnull(df: pd.DataFrame, *, label_col: str) -> pd.DataFrame:
    """Drop rows where the label is NaN, empty string, or the literal 'nan'."""
    if label_col not in df.columns:
        return df
    s = df[label_col].astype(str)
    mask = s.notna() & (s != "") & (s.str.lower() != "nan")
    return df[mask].reset_index(drop=True)
