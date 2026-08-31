"""Launch-day health dashboard for the F4D Results Reporting portal.

Read-only. Answers "is everything running fine?" at a glance:
  * the app responds (optional HTTP check),
  * SQL Server is reachable and the data parses,
  * FY26 submissions are actually coming in -- progress tally, per-section
    coverage, recent-activity pulse, and a live feed of the latest saves.

Uses python-tds (``import pytds``), the same pure-Python driver as the loader,
so it imports under the VDI's group-policy DLL block (no pyodbc / pandas).

Run on the VDI:

    $env:sql_username="EFI_Admin"; $env:sql_password="<password>"
    py health_check_pytds.py                 # one-shot dashboard
    py health_check_pytds.py --watch         # refresh every 30s (Ctrl+C to stop)
    py health_check_pytds.py --watch 15      # refresh every 15s

Optional app check -- set the portal URL and it will time an HTTP request:
    $env:F4D_PORTAL_URL="https://<your-posit-connect-app-url>"

Env overrides: sql_host, sql_database, sql_port, db_schema, F4D_TARGET_FY (FY26).
Nothing is ever written or deleted.
"""
import ast
import getpass
import os
import sys
import time

SCHEMA = os.environ.get("db_schema", "f4d")
TARGET_FY = os.environ.get("F4D_TARGET_FY", "FY26")

# Sections whose value is stored as a str(dict)/str(list) blob (vs. a plain
# scalar string like country / region_id / free text).
CORE_SECTIONS = ("region_id", "deliverables", "custom_indicators")


def connect():
    import pytds
    user = os.environ.get("sql_username") or input("SQL username: ").strip()
    password = os.environ.get("sql_password") or getpass.getpass("SQL password: ")
    return pytds.connect(
        os.environ.get("sql_host", "WBGMSSQLEFIP001"),
        os.environ.get("sql_database", "WBG"), user, password,
        port=int(os.environ.get("sql_port", "5800")),
        autocommit=False, login_timeout=15)


def scalar(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def is_blob(value):
    return bool(value) and value.lstrip()[:1] in "{["


def app_check():
    url = os.environ.get("F4D_PORTAL_URL")
    print("APP")
    if not url:
        print("  (set F4D_PORTAL_URL to time an HTTP request to the portal)")
        return
    import urllib.request
    t = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
        print(f"  UP  {url}")
        print(f"      HTTP {code} in {(time.time() - t) * 1000:.0f} ms "
              f"(any HTTP response means the server is serving)")
    except Exception as e:  # noqa: BLE001 - report whatever went wrong
        print(f"  !! UNREACHABLE  {url}\n     {e}")


def dashboard(cur):
    S, FY = SCHEMA, TARGET_FY
    server_now = scalar(cur, "SELECT GETDATE()")
    print(f"\n{'=' * 68}")
    print(f"F4D PORTAL HEALTH  --  server time {str(server_now)[:19]}")
    print(f"{'=' * 68}")

    app_check()

    print("\nDATABASE")
    print(f"  connected -> {os.environ.get('sql_host', 'WBGMSSQLEFIP001')}"
          f":{os.environ.get('sql_port', '5800')}  db="
          f"{os.environ.get('sql_database', 'WBG')}  schema={S}")
    total_grants = scalar(cur, f"SELECT COUNT(*) FROM {S}.trustfunds WHERE deleted=0")
    logins = scalar(cur, f"SELECT COUNT(*) FROM {S}.users WHERE deleted=0")
    print(f"  reference data: {total_grants} trust funds, {logins} logins")

    # Resolve the reporting fiscal year.
    cur.execute(f"SELECT id FROM {S}.fys WHERE fy=%s AND deleted=0", (FY,))
    fy_rows = cur.fetchall()
    if not fy_rows:
        cur.execute(f"SELECT fy FROM {S}.fys WHERE deleted=0 ORDER BY fy")
        avail = ", ".join(r[0] for r in cur.fetchall())
        print(f"\n  !! No fiscal year '{FY}'. Available: {avail}")
        print("     Set F4D_TARGET_FY to one of those and re-run.")
        return
    fy_ids = [r[0] for r in fy_rows]
    ph = ",".join(["%s"] * len(fy_ids))

    def dcount(where, params=()):
        return scalar(cur, f"SELECT COUNT(DISTINCT trustfund_id) FROM "
                      f"{S}.grant_info_long WHERE deleted=0 AND {where}", params)

    started = dcount(f"fiscal_year_id IN ({ph})", tuple(fy_ids))
    has_basic = dcount(f"fiscal_year_id IN ({ph}) AND field='region_id'", tuple(fy_ids))
    has_deliv = dcount(f"fiscal_year_id IN ({ph}) AND field='deliverables'", tuple(fy_ids))
    has_results = dcount(f"fiscal_year_id IN ({ph}) AND field='custom_indicators'", tuple(fy_ids))

    def bar(n):
        pct = (n / total_grants) if total_grants else 0
        filled = int(round(pct * 20))
        return f"[{'#' * filled}{'.' * (20 - filled)}] {n:>3}/{total_grants} ({pct * 100:4.0f}%)"

    print(f"\n{FY} SUBMISSION PROGRESS")
    print(f"  started (any save) {bar(started)}")
    print(f"  basic info         {bar(has_basic)}")
    print(f"  deliverables       {bar(has_deliv)}")
    print(f"  results indicators {bar(has_results)}")

    # Live pulse -- writes in the last hour / day (server clock).
    def acount(hours):
        return scalar(cur, f"SELECT COUNT(*) FROM {S}.grant_info_long "
                      f"WHERE deleted=0 AND updated_at >= DATEADD(hour,-{hours},GETDATE())")

    def agrants(hours):
        return scalar(cur, f"SELECT COUNT(DISTINCT trustfund_id) FROM {S}.grant_info_long "
                      f"WHERE deleted=0 AND updated_at >= DATEADD(hour,-{hours},GETDATE())")

    print("\nACTIVITY (all writes)")
    print(f"  last  1h : {acount(1):>4} saves across {agrants(1)} grant(s)")
    print(f"  last 24h : {acount(24):>4} saves across {agrants(24)} grant(s)")

    # Per-section coverage for the reporting year.
    print(f"\n{FY} SECTION COVERAGE (distinct grants with a save in each field)")
    cur.execute(f"SELECT field, COUNT(DISTINCT trustfund_id) FROM {S}.grant_info_long "
                f"WHERE deleted=0 AND fiscal_year_id IN ({ph}) "
                f"GROUP BY field ORDER BY COUNT(DISTINCT trustfund_id) DESC", tuple(fy_ids))
    for field, n in cur.fetchall():
        print(f"    {field:<28} {n}")

    # Live feed.
    N = 15
    print(f"\nLATEST {FY} SAVES (top {N})")
    cur.execute(f"SELECT TOP ({N}) g.updated_at, t.name, g.field, g.value "
                f"FROM {S}.grant_info_long g "
                f"LEFT JOIN {S}.trustfunds t ON t.id=g.trustfund_id "
                f"WHERE g.deleted=0 AND g.fiscal_year_id IN ({ph}) "
                f"ORDER BY g.updated_at DESC", tuple(fy_ids))
    rows = cur.fetchall()
    if not rows:
        print(f"  (no {FY} submissions yet -- waiting for the first TTL save)")
    else:
        print(f"  {'updated_at':<20} {'grant':<26} {'field':<22} {'bytes':>6}")
        for ts, name, field, value in rows:
            print(f"  {str(ts)[:19]:<20} {str(name)[:26]:<26} {field:<22} "
                  f"{(len(value) if value else 0):>6}")

    # Data integrity for the reporting year.
    cur.execute(f"SELECT value FROM {S}.grant_info_long "
                f"WHERE deleted=0 AND fiscal_year_id IN ({ph})", tuple(fy_ids))
    blobs = bad = 0
    for (value,) in cur.fetchall():
        if not is_blob(value):
            continue
        blobs += 1
        try:
            ast.literal_eval(value)
        except (ValueError, SyntaxError):
            bad += 1
    status = "OK" if bad == 0 else f"!! {bad} FAILED"
    print(f"\nINTEGRITY: {blobs} {FY} dict/list blobs parse -> {status}")
    print(f"\n{'=' * 68}\nread-only -- nothing was written")


def main():
    args = [a for a in sys.argv[1:]]
    watch = "--watch" in args
    interval = 30
    for a in args:
        if a.isdigit():
            interval = int(a)
    conn = connect()
    cur = conn.cursor()
    try:
        while True:
            dashboard(cur)
            if not watch:
                break
            print(f"\nrefreshing in {interval}s ... (Ctrl+C to stop)\n")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
