# Local development and demo seeds

These belong to neither deployed system. They fill a database with data to
develop or demo against — normally the local SQLite one.

Run them from the repo root with the venv's interpreter; each puts the repo root
on `sys.path` itself, so the working directory does not matter:

```bash
./venv/Scripts/python.exe dev/seed_dev.py
```

By default they use whatever `.env` / environment variables `connection.py`
finds, so **check `db_backend` before running one** — pointed at a real
database, the rebuild scripts below will wipe rows. For local work:

```
db_backend=sqlite
sqlite_path=f4d.db
```

| Script | What it creates |
|---|---|
| `seed_dev.py` | The minimum to make the app usable: one team, a TTL login, two fiscal years, a trust fund, one mapped indicator. Idempotent. |
| `seed_test_data.py` | Builds on `seed_dev.py` with enough content to exercise the reporting flows — mandatory and optional deliverables, a saved report, custom and archived entries. |
| `seed_haiti_example.py` | A real grant transcribed from the master workbook, as a realistic example to explore. **Clean rebuild** — wipes that grant's rows and recreates them. |
| `run_demo.ps1` | Starts Streamlit and exposes it through a Cloudflare quick tunnel, printing a public URL that lives as long as the window stays open. |

`run_demo.ps1` puts the app on the public internet with no authentication beyond
the app's own login form. **Demo data only — never point it at a real
database.** The URL is different every run.

The trust fund's name must equal the TTL's username: that is how the app
resolves which report a logged-in user is editing. The seeds already do this;
keep it in mind if you hand-edit rows.

Seeds for the Azure database are not here — they are in
[`deploy/azure/ops/`](../deploy/azure/ops/), because they belong to that system.
