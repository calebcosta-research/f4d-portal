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

`build_deploy_zip.py` excludes the venv, git, caches, local databases and logs,
the Posit deployment files (`manifest.json`, `.rscignore`), the `dev/` seeds and
this entire `deploy/` tree — the ops scripts are run from a workstation against
the database, not from inside the App Service. It also substitutes this
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

- **Azure SQL:** `db_backend=mssql`, `sql_driver=pymssql`, `sql_port=1433`, plus
  `sql_host` / `sql_username` / `sql_password` / `sql_database`, and `db_schema`
  if the tables need namespacing.
- **PostgreSQL flexible server:** `db_backend=postgres`, `sql_port=5432`,
  `db_schema=` (blank, so tables land in `public`).

Secrets belong in Key Vault and should reach the app as Key Vault references,
not as literal application settings.

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
