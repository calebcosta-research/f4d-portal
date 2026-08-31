# F4D Results Reporting portal

A Streamlit application where World Bank task teams report annual results for
F4D trust funds. One application, deployed to two places.

## The two systems

| | **Posit Connect** | **Azure** |
|---|---|---|
| Status | **Live.** This is what TTLs use. | Migration target, not yet in service. |
| Runs on | WB-managed Posit Connect | Azure App Service (Linux, Python) |
| Database | WB SQL Server, private schema | Azure SQL / PostgreSQL flexible server |
| Files | [`deploy/posit/`](deploy/posit/) | [`deploy/azure/`](deploy/azure/) |

The Azure target is meant to **replace** Posit Connect, not to run beside it
permanently. That is why the application itself is not forked: both deployments
run the same code from the repo root, and the per-system directories hold only
what actually differs — deployment mechanics, dependency sets, and the
operational scripts that talk to each system's database.

**Read the README in the relevant `deploy/` directory before deploying or
running anything against a database.**

## Layout

```
main.py, model.py, connection.py, f4d/     the application — shared by both systems
manifest.json, .rscignore, requirements.txt  Posit Connect's; must stay at the repo root
.streamlit/config.toml                     Streamlit server settings — shared (see note below)
batch_import.py, f4d/batch/                CSV/XLSX batch importer (CLI + reusable engine)
superadmin.py                              pre-refactor monolith; nothing imports it

deploy/posit/     the live system: deployment notes + its ops scripts
deploy/azure/     the new system: deployment script, its requirements, provisioning ask
dev/              local development and demo seeds — belongs to neither system
docs/             hosting and compliance background
```

Which system a file belongs to is decided by what it *talks to*, not where it
runs from. `deploy/posit/ops/` holds the scripts that read and write the live WB
SQL Server; `deploy/azure/ops/` holds the ones that load the Azure database.
Both are run from a workstation, not from inside the deployed app.

## How the app picks a database

`connection.py` reads environment variables — there is no per-system branch in
the application code:

| Variable | Meaning |
|---|---|
| `db_backend` | `mssql`, `postgres`, or `sqlite` |
| `sql_driver` | for `mssql` only: `pyodbc` (needs a system ODBC driver) or `pymssql` (self-contained) |
| `sql_host`, `sql_port`, `sql_username`, `sql_password`, `sql_database` | connection details |
| `db_schema` | schema to namespace the tables into; blank for sqlite and postgres |

Concrete values are never committed. Each system's README says where its values
are set.

## Local development

```bash
python -m venv venv && ./venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env          # then edit; .env is gitignored
./venv/Scripts/python.exe dev/seed_dev.py
./venv/Scripts/streamlit.exe run main.py
```

See [`dev/README.md`](dev/README.md) for the other seeds.

## A note on `.streamlit/config.toml`

It is shared, and it disables XSRF protection and CORS checks — settings that
were added for running behind an Azure App Service proxy but that also apply to
the live Posit Connect deployment. That is a coupling worth resolving; it was
left alone during the split because changing it changes live behaviour. See
[`deploy/posit/README.md`](deploy/posit/README.md).
