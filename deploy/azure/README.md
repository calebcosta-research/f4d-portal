# Azure — the new system

The migration target: the whole application on Azure, with Posit Connect
retired. Not in service yet.

Target architecture: **App Service** (Linux, Python 3.11) running Streamlit,
**Azure SQL Database**, **Key Vault** for secrets, **Application Insights** for
monitoring. A working reference deployment of this shape has been built and run
end to end (on a personal subscription, with demo data only), which is where the
specifics below come from.

## Contents

| Path | What it is |
|---|---|
| `requirements.txt` | The App Service dependency set. **Not** the repo-root one, which is Posit Connect's. |
| `build_deploy_zip.py` | Builds `app.zip` from the shared application at the repo root. |
| `provisioning_request.md` | The ask to the platform team, for infrastructure this account cannot create itself. |
| `ops/seed_all_from_master.py` | Bulk-loads every trust fund from the master workbook. Uses pandas + SQLAlchemy — fine here, unlike the Posit ops scripts. |
| `ops/seed_demo_fund.py` | Seeds one fictional trust fund with two years of data, for demos. `--delete` removes it. |
| `ops/export_live_to_sql.py` | Exports the live database to loadable `.sql` files, for migrating the running system onto Azure. Pure Python (pytds, no pandas) because it runs on the VDI. |

The application itself is not here — it is at the repo root, shared with the
live system. See the [root README](../../README.md).

## Deploying

```bash
./venv/Scripts/python.exe deploy/azure/build_deploy_zip.py
az webapp deployment source config-zip -g <resource-group> -n <app-name> --src app.zip
```

**Use `config-zip`, not `az webapp deploy --type zip`.** Only `config-zip` runs
the Oryx build that installs dependencies; the other form uploads the files and
the app then fails with `No module named streamlit`.

`build_deploy_zip.py` packs the **committed** files at a git ref (default
`HEAD`; pass another as an argument), never the working tree, so uncommitted
edits and stray local files can't ship. It leaves out the Posit deployment files
(`manifest.json`, `.rscignore`), the `dev/` seeds, `docs/`, this entire
`deploy/` tree — the ops scripts are run from a workstation against the
database, not from inside the App Service — and workstation tooling the app
never imports (the batch importer and `.env.example`). It also substitutes this
directory's `requirements.txt` into the zip in place of the root one.

## App Service configuration

Startup command:

```
python -m streamlit run main.py --server.port 8000 --server.address 0.0.0.0
```

Settings: **WebSockets on** (Streamlit needs them), **Always On** on,
`WEBSITES_PORT=8000`, and `SCM_DO_BUILD_DURING_DEPLOYMENT=true`.

Application settings for the database — the same variables `connection.py` reads
everywhere, so no code changes when switching backends:

- **Azure SQL, managed identity** (no password anywhere): `db_backend=mssql`,
  `sql_driver=pyodbc`, `sql_auth=msi`, `sql_port=1433`, `sql_host`,
  `sql_database`, `db_schema=dbo`. Add `sql_msi_client_id` (the identity's
  Client ID) for a user-assigned identity. Needs ODBC Driver 18, which the
  App Service Python 3.12 image (Debian 12) already has — checked over SSH
  with `odbcinst -q -d` — and the identity must reach the database, e.g. via
  the WB READER/WRITER AD groups, *provided those groups are themselves
  database users*.
- **Azure SQL, SQL login:** `db_backend=mssql`, `sql_driver=pymssql`,
  `sql_port=1433`, plus `sql_host` / `sql_username` / `sql_password` /
  `sql_database`, and `db_schema=dbo`. Works on the stock image.

Always set `db_schema` explicitly. Left unset it defaults to
`TF_RESULTS_REPORTING`, which won't exist on a new database.
- **PostgreSQL flexible server:** `db_backend=postgres`, `sql_port=5432`,
  `db_schema=` (blank, so tables land in `public`).

Secrets belong in Key Vault and should reach the app as Key Vault references,
not as literal application settings.

### Application Insights

`f4d/telemetry.py` exports the app's own logs, crashes and a few named events
(logins, page views, saves, submissions). It is off until a connection string is
set.

- `APPLICATIONINSIGHTS_CONNECTION_STRING` — from the App Insights resource.
- `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD` — only if the
  resource has local authentication disabled. Telemetry is then sent with the
  App Service's managed identity, which needs the *Monitoring Metrics Publisher*
  role on the resource. Add `;ClientId=<guid>` for a user-assigned identity.

The app configures telemetry itself, so App Service's own automatic Python
instrumentation should stay off; with both on, everything is reported twice.
Events carry internal numeric IDs and page names only — no usernames, passwords
or form content. The SDK's own usage reporting to Microsoft ("statsbeat") is off
by default; set `APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL=false` to allow it.

Browser-side end-user monitoring is not implemented: Streamlit gives the app
little control over the page's JavaScript.

### Passwords

Stored as salted PBKDF2-SHA256 hashes (`f4d/passwords.py`, standard library
only). Login still accepts a legacy plain-text value and replaces it with a hash
on the next successful login, so an older database keeps working while it
migrates.

`ops/export_live_to_sql.py` hashes passwords on export, so a database loaded
from it never holds plain text. For one loaded from an older export, run the
`98_hash_existing_passwords.sql` it writes; it only touches rows still in plain
text.

**Never write hashed passwords into the live Posit database.** Posit runs `main`,
which compares plain text, so a hash there locks that user out of the live
system. That is why `deploy/posit/ops/seed_from_master_pytds.py` still writes
plain text.

### Excel export to Blob Storage

`f4d/reporting_export.py` refreshes a workbook in Blob Storage after each save
and submit, on a background thread. Two auth modes:

- `F4D_STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net` uses the App
  Service's managed identity, which needs the *Storage Blob Data Contributor*
  role on the account. **This is the mode to use** — it is the only one that
  works when the storage account has shared-key access disabled, which is the
  WB default.
- `AZURE_STORAGE_CONNECTION_STRING` embeds an account key. Local development
  only.

Also set `F4D_EXPORT_CONTAINER` and `F4D_EXPORT_BLOB`. With neither auth
variable set the upload is a no-op, which is how it behaves on Posit Connect.

## Provisioning

The WB Azure account can *deploy into* existing infrastructure but cannot
*create* it — creating an App Service plan, a web app, or a database is denied
by role. `provisioning_request.md` is the request for the platform team; the
reference deployment proves the exact spec it asks for.

## Gotchas learned on the reference deployment

- A fresh subscription needs resource providers registered before anything can
  be created: `az provider register --namespace Microsoft.Web` (likewise
  `Microsoft.DBforPostgreSQL` and `Microsoft.Storage`).
- Regional availability bites: PostgreSQL offers were restricted in several
  regions, and App Service B1 quota was zero in others. Expect to shop around.
- `pyodbc` installs on Linux but has no ODBC driver behind it in the stock App
  Service image. Use `pymssql`, or ship `msodbcsql18` in a custom container.
  Note that `pymssql` cannot do managed-identity auth to the database — if the
  architecture requires that, `pyodbc` plus a custom image is the only path.
- `connection.py` builds its engine once per process. It used to rebuild the
  engine and run `create_all` on every call, which was survivable locally and
  catastrophic across regions.
