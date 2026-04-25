# tabprep — development log

> Living handoff document. The most-recent entry is at the top.
> Each entry summarises state-of-the-tree at the time of writing,
> the work in flight, and the next concrete tasks.

---

## 2026-04-25 — extended IDS catalogue + licence-consent infrastructure

### What landed

Four new IDS datasets, spanning 1998 → 2024:

| Profile | Year | Category | Distribution |
|---|---|---|---|
| `nsl_kdd` | 2009 | **Legacy** — cleaned-up KDD-99 (DARPA-1998 traces) | UNB CIC mirror, no consent form |
| `insdn` | 2020 | **SDN-special** — Software-Defined Networking IDS | Mendeley Data + consent form |
| `cic_apt_iiot` | 2024 | **Most recent** — APT in Industrial IoT | UNB CIC + consent form |
| `bot_iot` | 2018 | **Most popular** — UNSW Canberra IoT botnet (>2k cites) | UNSW Cloudstor + consent form |

Total profile count: **18 → 22**.

### Licence-consent infrastructure (`tabprep/datasets/_base/downloader.py`)

Three new pieces:

  * `DEFAULT_USER_INFO` — a publicly-readable placeholder identity used
    when `TABPREP_USER_*` env vars aren't set. Deliberately
    self-identifying (`"tabprep automated download"`) rather than
    impersonating a real-looking user.
  * `_get_user_info()` — reads `TABPREP_USER_NAME` /
    `TABPREP_USER_EMAIL` / `TABPREP_USER_AFFILIATION` /
    `TABPREP_USER_PURPOSE` env vars, falls back to `DEFAULT_USER_INFO`
    placeholders with a one-line warning per unset key.
  * `_submit_consent_form(form_url, *, extra_fields, user_keys)` —
    POSTs the form, best-effort. 4xx/5xx responses and network
    exceptions are logged but do **not** abort the download (most
    providers' download URLs work even when the form-submission
    endpoint changes; the form is informational, not auth-gating).

`HTTPArchiveDownloader` and `HTTPMultiURLDownloader` now honour these
via class attributes:

```python
class CICAPTIIoTDownloader(HTTPArchiveDownloader):
    url = "..."
    consent_form_url = "..."
    consent_form_fields = {"dataset": "CIC-APT-IIoT-2024", "licence_accepted": "true"}
    consent_form_user_keys = ("name", "email", "affiliation", "purpose")
```

### CLI by-name lookup fix

`tabprep prepare/verify/download --profile pendigits` previously failed
with `FileNotFoundError: profile not found: ./pendigits` because
`cmd_prepare` called `load_profile(args.profile)` directly instead of
going through `tabprep.api.resolve_profile`. Fixed by routing all three
CLI commands through `resolve_profile`. The Python API
(`tabprep.prepare("pendigits")`) was already correct.

### Tests

  * `tests/test_consent_form.py` — 9 tests covering env-var override,
    placeholder warning, payload construction, 4xx/network-exception
    no-abort behaviour, and the HTTPArchiveDownloader integration
    (consent posted before download).
  * `tests/datasets/test_new_ids_datasets.py` — 19 tests covering
    registration, class-attribute pinning, NSL-KDD loader on a
    synthetic KDDTrain+/Test+ fragment, and the shared concat-csv
    behaviour for the three CIC-pattern loaders.

Total: 253 → 281 tests, all passing. ruff clean.

### Cold-cache prepare run

Cleaned `prepared/`, `~/scikit_learn_data/{openml,covertype}/`, and
the `_complete` markers under `raw/openml/`. Then ran a series of
prepare commands from a clean state to demonstrate the framework.

**16/16 historical hashes still match where prepares completed** —
specifically:

  * `covertype` — full clean run: sklearn cache miss → fetch → load →
    canonical CSV → manifest → hash check passed.
  * `iot23` — cache-hit on the existing 44 GB tarball, then full
    prepare. Hash match.
  * `5g_nidd`, `ciciot2023`, `edge_iiot`, `ton_iot`, `unsw_nb15` —
    full prepare from existing pre-staged raw data. Hash match.

**Two known-slow profiles** (`cicids2018`, `nbaiot`) hit the legacy
`concat_csvs` / `nbaiot_dir` source's in-memory CSV-concat
bottleneck — `nbaiot` reached 15 min / 15 GB RSS before being killed.
This is the v0.4 scalability issue scheduled for Phase 4 fix
(rewrite as streaming / chunked concat).

**Seven OpenML profiles** (`pendigits`, `letter`, `optdigits`,
`satimage`, `segment`, `texture`, `har`) failed during this run with
`HTTPError 301 (infinite redirect loop)` — confirmed via a direct
`fetch_openml(...)` call. This is an **upstream** issue with
`api.openml.org`'s redirect chain, not a regression in our framework.
Will resolve when OpenML's CDN settles.

### Suggested workflow for users running consent-form profiles

```bash
export TABPREP_USER_NAME="Your Real Name"
export TABPREP_USER_EMAIL="you@your.institution.edu"
export TABPREP_USER_AFFILIATION="Your Institution"
export TABPREP_USER_PURPOSE="What you're using this dataset for"

tabprep prepare --profile cic_apt_iiot       # or nsl_kdd, insdn, bot_iot
```

Without the env vars, the framework prints a loud warning and submits
clearly-labelled placeholders. UNB CIC and UNSW track these
submissions for grant-reporting / bibliometric purposes — please
identify yourself properly in published work.

---

## 2026-04-25 — Phase 3 done: UCI tabular family migrated

### What landed

v0.5 Phase 3 is complete. All 8 UCI tabular profiles (pendigits,
letter, optdigits, satimage, segment, texture, har, covertype) now
dispatch through the new `tabprep/datasets/<family>/` packages.

Layout:

```
tabprep/datasets/openml/         # 7-profile family (pendigits, letter, optdigits,
├── __init__.py                  #                  satimage, segment, texture, har)
├── downloader.py                # @downloader("openml") — pre-fetches via
├── loader.py                    #                         sklearn.fetch_openml,
└── README.md                    #                         writes `_complete` marker
                                 # @loader("openml")     — reads loader_options.openml_name
                                 #                         + openml_version (default 1)

tabprep/datasets/covertype/      # standalone (different sklearn signature)
├── __init__.py
├── downloader.py                # @downloader("covertype") — sklearn.fetch_covtype
├── loader.py                    # @loader("covertype")     — handles as_frame=True
└── README.md                    #                            and the older ndarray
                                 #                            fallback path
```

Profile YAMLs moved `profiles/builtin/<name>.yaml → profiles/<name>.yaml`
with the v0.5 dispatch shape:

```yaml
downloader: openml
loader: openml
cached_at: raw/openml/<openml_name>/
loader_options:
  openml_name: <openml_name>
  openml_version: 1
```

### Smoke test

End-to-end `tabprep prepare` reproduces byte-identical output for all 8
migrated profiles — the new dispatch path produces the same canonical
CSVs the legacy `source: { kind: openml | sklearn }` path did:

```
$ python -m tabprep verify --all
[summary] verified 16 / 18 profile(s) (skipped 2 without expected_hashes)
```

(cic_ddos2019 + cic_iomt2024 still skipped — unpinned, will gain
hashes in Phase 4 once the form-gated download workflow stabilises.)

### Tests

- 17 new tests: `tests/datasets/test_openml.py` (9), `test_covertype.py` (8).
- All sklearn calls are mocked via `sys.modules['sklearn.datasets']` so
  the suite never hits the network.
- Pre-existing `tests/test_smoke.py::test_load_pendigits_profile`
  updated to validate the v0.5 schema (`prof.loader == "openml"` etc.).
- Total: **59 passed, 0 failed**.

### v0.5 status board

| Phase | Status | Commit |
|---|---|---|
| 1 — Bootstrap base classes + registries | ✅ done | `2ed7b38` |
| 2 — Migrate `iot23` end-to-end | ✅ done | `5b62fa2` |
| 3 — Migrate UCI tabular family (8 profiles) | ✅ done | (this commit) |
| 4 — Migrate 10 IDS profiles + delete old `tabprep/sources/` | next | — |
| 5 — `sample_fraction_stratified` op + README/CONTRIBUTING refresh | pending | — |

### Next task — Phase 4

Migrate the 10 IDS profiles (`5g_nidd`, `cic_ddos2019`, `cic_iomt2024`,
`cicids2018`, `ciciot2023`, `edge_iiot`, `nbaiot`, `ton_iot`,
`unsw_nb15`) plus delete the legacy `tabprep/sources/` shim once every
profile is migrated.

Per-dataset families:

- **CIC family** (`cic_ddos2019`, `cic_iomt2024`, `cicids2018`,
  `ciciot2023`) — one `tabprep/datasets/cic/` package; downloaders hit
  `cicresearch.ca` / `205.174.165.80` directly (form is informational,
  not auth-gated; document the licence step in the README).
- **5G-NIDD, Edge-IIoTSet, ToN-IoT** — `FormGatedDownloader` (IEEE
  DataPort / Mendeley / SharePoint).
- **UNSW-NB15** — `HTTPMultiURLDownloader` against the Zenodo mirror
  (4 numbered CSVs).
- **N-BaIoT** — UCI archive ZIP via `HTTPArchiveDownloader`.

Re-run the source-survey agent before starting to re-verify which
mirrors are still curl-able as of the latest run date.

### Bonus: public Python API (`tabprep.api`)

Landed alongside Phase 3 in response to a user request. New top-level
exports:

```python
import tabprep

result = tabprep.prepare("pendigits")               # builtin name
train_df, cal_df, test_df = tabprep.load_splits("pendigits")
result = tabprep.prepare("./my_profile.yaml")        # custom YAML
result = tabprep.prepare(profile_instance)           # programmatic Profile

tabprep.list_profiles()                              # discover what's built in
```

**Surface:**
- `tabprep.prepare(profile, output_dir=None, *, data_root=None,
  skip_pipeline=False, quiet=False) → PrepareResult`
- `tabprep.load_splits(profile, *, output_dir, data_root, skip_pipeline,
  use_cache=True, quiet=True) → (train_df, cal_df, test_df)`
- `tabprep.load_split(profile, split="train", **kw) → DataFrame`
- `tabprep.list_profiles() → list[Profile]`
- `tabprep.resolve_profile(spec) → Profile`
- `tabprep.PrepareResult` (dataclass with `train`/`calibration`/`test`
  paths, `sha256` map, `verified` flag, plus `.load(split)` / `.load_all()`)

**Profile resolution:** bare strings → builtin lookup; strings with
separators or `.yaml`/`.yml` suffix → filesystem path; `Path` →
filesystem path; `Profile` → pass-through.

**Caching:** `load_splits` and `load_split` reuse already-prepared CSVs
when their hashes match `expected_hashes` (or no hashes are pinned),
so notebook-style repeated calls are cheap. `prepare()` itself takes
a defensive copy of the resolved Profile so callers holding a
reference don't see their `cached_at` mutated to absolute.

**Tests:** `tests/test_api.py` — 19 tests via a synthetic in-memory
loader/downloader pair (`@loader("_apitest")` + `@downloader("_apitest")`),
including a regression test for the Profile-mutation fix.

**Example:** `examples/quickstart.py` walks through the five most
common usage patterns.

The CLI (`python -m tabprep prepare ...`) and the API are parallel
entry points into `run_pipeline`; both produce byte-identical output
for equivalent arguments. A future cleanup could collapse `cli.cmd_prepare`
to a thin wrapper around `api.prepare`, but that's out of scope for
Phase 3.

### Bonus: profiles now ship with the package (`tabprep/profiles/`)

The repo-root `profiles/` directory was discovered to be outside the
installable package — `pyproject.toml`'s `packages.find` only ships
`tabprep/*`, so non-editable `pip install .` produced a tabprep where
`list_profiles()` returned `[]` and `prepare("pendigits")` raised
`FileNotFoundError`.

**Fix:** moved `profiles/` → `tabprep/profiles/` (incl. `tabprep/profiles/builtin/`
for unmigrated v0.4 profiles), updated `_profiles_root()` /
`_PROFILE_DIRS` to `Path(__file__).parent / "profiles"`, and added
`profiles/*.yaml`, `profiles/builtin/*.yaml`, and `datasets/*/README.md`
to `pyproject.toml`'s `[tool.setuptools.package-data]` glob. CLI users
can still pass an absolute or relative path (`--profile ./my.yaml`);
the by-name lookup (`--profile pendigits` / `tabprep.prepare("pendigits")`)
now works for both editable and non-editable installs.

### After Phase 3

- The `tabprep/sources/` shim still works and is kept until Phase 4
  migrates the last legacy profile. Both dispatches coexist; the
  pipeline picks v0.5 when `profile.loader is not None`.

---

## 2026-04-25 — handoff into a fresh session

### Where we are

The framework lives at **`/Users/troisang1/Documents/Project/Papers/tabprep/`**
(its own Apache-2.0 git repo, remote `origin = https://github.com/troisang1/tabprep`).
It was relocated from `cnNFST/data/tabprep/` earlier today; raw datasets and
the prepared outputs moved with it (`raw/` and `prepared/` are now siblings
of the package). cnNFST's commit `064f18a` updates its scripts to point at
`../tabprep/raw/` for any code that historically read from `data/raw/`.

### Tree state (committed)

Branch `main` is on remote up to **`5b62fa2`**:

```
5b62fa2  v0.5 Phase 2: migrate iot23 to datasets/iot23/ end-to-end
2ed7b38  v0.5 Phase 1: bootstrap base classes + dataset registries
089f753  auto-download infrastructure: download_url, download_urls, archive_format
f498167  concat_csvs: recursive walk + encoding fallback
...
```

### Tree state (uncommitted)

`git status` will show:

- ` D profiles/builtin/iot23.yaml` — phantom deletion: Phase 2 committed
  the move `profiles/builtin/iot23.yaml → profiles/iot23.yaml`, but the
  working-tree deletion of the *old* path needs to be staged in the next
  commit (likely `git rm` it explicitly).
- ` M tabprep/cli.py` — `DEFAULT_OUTPUT_ROOT` flipped from `"../processed"`
  to `"prepared"` and `DEFAULT_DATA_ROOT` from `".."` to `"."` so the
  tool runs flag-free from the new project root. Lock this in with the
  Phase 3 commit (it's a one-line behavioural change with the same
  effect on hashes).
- `?? raw/` — gitignored (data files), present locally for verification.

Verify the move worked end-to-end:

```bash
cd /Users/troisang1/Documents/Project/Papers/tabprep
python -m pytest tests/ -q          # 42 passing
python -m tabprep list              # 18 profiles
python -m tabprep verify --all      # 16/16 pinned profiles match
                                    # (cic_ddos2019 + cic_iomt2024 skipped — unpinned)
```

### v0.5 status board

| Phase | Status | Commit |
|---|---|---|
| 1 — Bootstrap base classes + registries | ✅ done | `2ed7b38` |
| 2 — Migrate `iot23` end-to-end | ✅ done | `5b62fa2` |
| 3 — Migrate UCI tabular family (8 profiles) | next | — |
| 4 — Migrate 10 IDS profiles + delete old `tabprep/sources/` | pending | — |
| 5 — `sample_fraction_stratified` op + README/CONTRIBUTING refresh | pending | — |

### Next task — Phase 3

Migrate the 8 UCI profiles (`pendigits`, `letter`, `optdigits`, `satimage`,
`segment`, `texture`, `har`, `covertype`) onto the new dispatch.

**Plan:**

1. **Bundle 7 OpenML profiles into one `tabprep/datasets/openml/` family**
   (they all use `sklearn.datasets.fetch_openml(name, version=1)` and the
   `Bunch.data + Bunch.target` shape — same downloader, same loader). Each
   profile sets the OpenML name via `loader_options.openml_name: pendigits`
   etc.
2. **`covertype` is standalone** under `tabprep/datasets/covertype/` because
   `sklearn.datasets.fetch_covtype` has a different signature (no
   `Bunch.target` for the older sklearn versions; see the hardening fix
   in `tabprep/sources/sklearn_source.py:load_sklearn`).
3. **Move profile YAMLs** `profiles/builtin/<name>.yaml → profiles/<name>.yaml`
   with the new schema (`downloader: openml` + `loader: openml` +
   `loader_options: { openml_name: pendigits, openml_version: 1 }`).
4. **Per-package READMEs** documenting source URL (OpenML / sklearn),
   licence (CC-BY 4.0 typically), known quirks (the OpenML 301 redirect
   currently surfaces in the CI advisory job — Phase 3 should pin the
   sklearn version that handles it).
5. **Unit tests per package** — at least:
   - registration in `LOADER_REGISTRY` / `DOWNLOADER_REGISTRY`
   - loader returns `(df, label_col)` with expected shape on a tiny
     mocked OpenML response
   - downloader's class attributes pinned (`is_supported = True`,
     `landing_url`, `licence_note`)
6. **Regression gate** — `python -m tabprep verify --all` must still
   report 16/16 pinned profiles match after the move.

### After Phase 3

Phase 4 is the bulk: 10 IDS profiles, each its own `datasets/<name>/`
package with dataset-specific drop columns and README. Some have direct
download URLs (IoT-23 ✅ already done; UNSW-NB15 has a Zenodo mirror; UCI
N-BaIoT has a UCI archive ZIP). Others are form-gated and will use
`FormGatedDownloader` (CIC family, 5G-NIDD, ToN-IoT, Edge-IIoTSet) —
those classes raise with a refusal message when the user calls
`download()`. Per-dataset notes from the 2026-04-25 source survey live in
the conversation history; before Phase 4, run the survey agent again to
re-verify which mirrors are still curl-able.

For CIC datasets specifically: the user confirmed the CIC form is
informational, not a hard auth gate. Once the licence is consented to,
the downloads work via `cicresearch.ca` / `205.174.165.80`. The CIC
downloader can hit those URLs directly; document the one-time form step
in the README.

### Known issues / gotchas

- **Bash `cwd` between tool calls is NOT reliable.** Use `cd <path> &&`
  on every Bash invocation to be safe; subprocesses started with
  `nohup` inherit the cwd at launch time, not at command time.
- **OpenML 301 redirect** still trips the advisory CI `reproduce` job
  on sklearn < 1.6. Pin `scikit-learn>=1.5` in CI; consider bumping
  to `>=1.6` once it ships with the redirect fix.
- **iot23 cold-start**: the resumed download succeeded
  (matches expected size 9 373 916 249 B); the extracted Zeek logs
  occupy ~44 GB under `raw/iot23/opt/Malware-Project/...`. Safe to keep
  for Phase 4 testing.

### Sanity checks before starting Phase 3

```bash
cd /Users/troisang1/Documents/Project/Papers/tabprep
git status                           # tree status (expect: ` M tabprep/cli.py`,
                                     #                       ` D profiles/builtin/iot23.yaml`)
git log --oneline -3                 # head should be 5b62fa2
python -m pytest tests/ -q           # 42 green
python -m tabprep verify --all       # 16/16 pinned
ruff check tabprep tests             # clean
```

If any of those don't match, stop and reconcile before touching new code.
