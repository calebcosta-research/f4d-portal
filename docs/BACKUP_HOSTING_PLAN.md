# Backup hosting plan — self-host the F4D portal

**Use this only if WB Posit Connect access does not come through.** Posit Connect
remains the preferred path (WB-managed, ~$0 to you, handles auth/audit). This is
the contingency.

**Scope guardrail:** non-classified data only. If the data is ever classified,
this plan does **not** apply — it must go on WB-managed infrastructure.

---

## Target setup

Two viable shapes. Pick one when you execute:

| | **A. Single VM + PostgreSQL** | **B. Azure (matches prod)** |
|---|---|---|
| Compute | 4 GB / 2 vCPU VM (DigitalOcean / AWS Lightsail) | App Service B2 (Linux, Python) |
| Database | PostgreSQL on the same box (or managed PG) | Azure SQL (S0) |
| DB code change | ~10 lines added to `connection.py` (+ `psycopg2-binary`) | **none** — app already speaks `mssql` |
| Front door | Cloudflare named tunnel + Access (email login wall) | Entra ID / IP restriction + HTTPS |
| ~Cost / month | **~$24** (bump to 8 GB ≈ $48 for the deadline week) | **~$30–50** |

**Sizing note for ~300 trust funds / users:** the data is tiny (~tens of MB).
The constraint is Streamlit concurrency, not storage — a 4 GB box handles a
steady stream of users; size up to 8 GB for the reporting-deadline crunch.

---

## Prerequisites — do these regardless (they also help a Posit deploy)

- [x] **`requirements.txt` fixed** — `python-dotenv` (not `dotenv`) + pinned versions. *(done 2026-06-15)*
- [ ] **Password hashing** — replace plaintext `user.password == password`. Basic hygiene with 300 real accounts, independent of classification.
- [ ] **`eval()` → safe parsing** — remove the code-execution hole in the EAV readers.
- [ ] **Batch user provisioning** — generate the ~300 TTL logins + their trust funds from the source list (reuse the `f4d/batch/` engine), rather than by hand.

## Self-host-specific — do only when executing this plan

- [ ] **Database:** Azure SQL (zero code change) **or** add a PostgreSQL backend to `connection.py` (`db_backend=postgres`) + `psycopg2-binary`. **Do not use SQLite** for a multi-user run — its single-writer lock causes "database is locked" errors under concurrency.
- [ ] Provision compute (VM or App Service).
- [ ] Set secrets as **environment variables** (`db_backend`, `sql_*`, admin creds) — never a committed `.env`.
- [ ] Seed reference data + batch-create users/trust funds.
- [ ] Deploy + smoke test.
- [ ] Put a login wall in front (Cloudflare Access or Entra ID).
- [ ] **Teardown after the month** — destroy the resources to stop billing.

---

## Runbook A — single VM + PostgreSQL (cheapest)

1. Provision a 4 GB Ubuntu VM (DigitalOcean droplet or AWS Lightsail), ~$24/mo.
2. Install Python 3.11+, clone the repo, create a venv, `pip install -r requirements.txt psycopg2-binary`.
3. Install PostgreSQL on the box (or use a managed PG). Create a database + user.
4. Add the Postgres branch to `connection.py` (`db_backend=postgres` → `postgresql+psycopg2://...`). ~10 lines.
5. Set env vars: `db_backend=postgres`, connection creds, `super_admin_*` / `f4d_admin_*`.
6. Run the seed + batch user/trust-fund import.
7. Run Streamlit headless on :8501 as a `systemd` service so it restarts on reboot.
8. Front it with a Cloudflare **named** tunnel (stable URL) + **Access** (email login wall).
9. Smoke test, then share the URL with the ~300 TTLs.

## Runbook B — Azure (matches the eventual prod stack, no DB code change)

1. Create an App Service (Linux, Python) B2 + an Azure SQL database (S0).
2. Deploy the code (git push or zip deploy).
3. Set App Service application settings (env vars):
   `db_backend=mssql`, `sql_host=<name>.database.windows.net`, `sql_username`,
   `sql_password`, `sql_database`, `sql_port=1433`, `db_schema=TF_RESULTS_REPORTING`.
4. Run the seed + batch user/trust-fund import against Azure SQL.
5. Restrict access (Entra ID auth or IP allow-list); HTTPS is on by default.
6. Teardown after the month.

---

## The honest summary

Money is the easy part (~$25–50 for the month). The work that gates a real
multi-user run is the three prerequisites above — **password hashing, the
`eval` fix, and batch user provisioning** — plus swapping SQLite for a real
database. None are large, and all except the Postgres branch also benefit a
Posit deploy, so they're safe to do now while the Connect access is pending.
