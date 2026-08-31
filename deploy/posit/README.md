# Posit Connect — the live system

This is the deployment TTLs are using. Treat changes to anything it depends on
as production changes.

Host: WB-managed Posit Connect (internal network only). Database: the WB SQL
Server, in a private schema inside an existing database — the app's SQL login
is not permitted to `CREATE DATABASE`, so the schema is the isolation boundary.

The concrete host, database, schema and login are **not committed**. They are
set on the content item under **Settings > Vars**, and recorded in the internal
runbook. This repo is public.

## Files that belong to this system

Three of them cannot move, because Connect's git-backed deploy reads them from
fixed paths at the repo root:

| File | Why it is pinned to the root |
|---|---|
| `manifest.json` | Lists every bundled file by **root-relative** path, and pins `entrypoint: main.py` and `package_file: requirements.txt`. |
| `requirements.txt` | The path `manifest.json` names as the package file. This is the **Posit** dependency set — Azure's is `deploy/azure/requirements.txt`. |
| `.rscignore` | Bundle exclusions; read from the bundle root. |

Everything else this system needs is the shared application at the repo root.
This directory holds the notes and the ops scripts.

## Deploying

Connect pulls from `main` of the GitHub repo. **It does not deploy on push.**

1. Push to `main`.
2. In Connect, open the content item and trigger the update (*Update Now* / git pull).
3. Open **Git details** and confirm the deployed commit SHA equals `main`'s HEAD.

Step 3 is not optional. Several reported "bugs" after launch were fixes that
were already in the code but not yet in the running bundle.

If you add a file the app imports at runtime, **add it to `manifest.json`** —
files absent from that list are not bundled, and the failure shows up as an
`ImportError` at page render, which on Connect reads to the user as a logout.

## Operational scripts (`ops/`)

These run from the WB **VDI**, which is the only place that can reach the
production database. The VDI is locked down in ways that dictate how they are
written:

- No git. Fetch each script over HTTPS instead:
  `Invoke-WebRequest https://raw.githubusercontent.com/calebcosta-research/f4d-portal/main/deploy/posit/ops/<script>.py -OutFile <script>.py`
  *(These paths changed in the repo split — the scripts used to be at the repo root.)*
- Run with the `py` launcher; a bare `python` hits a Microsoft Store stub.
- PowerShell is in ConstrainedLanguage mode.
- Group policy blocks unsigned compiled DLLs, so **any package with a C
  extension fails at import** — no pandas, numpy, pyodbc or pymssql.

Hence every script here is **pure Python: `pytds` + `openpyxl` only**. Install
with `py -m pip install python-tds openpyxl` (no admin needed). Credentials come
from `$env:sql_username` / `$env:sql_password`; nothing prompts for them in a
way that would put them in shell history.

| Script | What it does |
|---|---|
| `seed_from_master_pytds.py` | Loads all trust funds from the master workbook into the schema. Additive by default; `F4D_WIPE=YES` does a guarded full refresh; `F4D_DRYRUN=1` parses only. |
| `verify_saves_pytds.py` | Read-only. No arguments gives an overview; a trust fund number drills into one grant and decodes its stored blobs. |
| `health_check_pytds.py` | Launch dashboard — reporting progress, activity, latest saves, integrity checks. `--watch [secs]` to auto-refresh. |
| `scan_cross_grant_dupes_pytds.py` | Read-only. Finds grants whose answers were contaminated by the cross-grant session-state leak. |
| `clear_test_submission_pytds.py` | Deletes one grant's rows for one fiscal year. Dry-run by default, writes a backup file, and requires a typed confirmation. |
| `download_f4d_data.py` | Read-only. Exports everything to a formatted Excel workbook, merged with the M&E portfolio spreadsheet. |

`download_f4d_data.py` is the export path that works here. The in-app Excel
export to Azure Blob (`f4d/reporting_export.py`) does **not** work from Connect —
outbound network access is blocked — so it silently no-ops.

## Open items

- **`.streamlit/config.toml` is shared and disables XSRF protection and CORS
  checks on this live deployment.** Those settings were written for an Azure App
  Service proxy. Splitting them per-system changes live behaviour, so it was
  deliberately left out of the repo split. Worth deciding on its own.
- **`requirements.txt` still installs dependencies this system never uses** —
  `azure-storage-blob`, `azure-identity` and `psycopg2-binary`. As of the split
  the Azure SDK is imported lazily, so they are safe to remove; that is a
  production dependency change and deserves its own commit and a deploy check.
- Passwords are still stored and compared in plaintext.
