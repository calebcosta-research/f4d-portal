"""Verify that TTL submissions are actually landing in the WB SQL Server DB.

Read-only sanity check for go-live. Connects to WBG.<schema> with python-tds
(``import pytds``) -- the same pure-Python driver the loader uses, because it is
the only DB driver that imports under the VDI's group-policy DLL block (no
pyodbc / pymssql / pandas). Nothing is written or deleted.

Run on the VDI:

    $env:sql_username="EFI_Admin"; $env:sql_password="<password>"
    py verify_saves_pytds.py                # overview: counts + latest saves
    py verify_saves_pytds.py TF0D2220       # focus: one grant, decoded

Server / db / port / schema default to the known production values and can be
overridden by env (sql_host, sql_database, sql_port, db_schema). Credentials are
read from env (sql_username / sql_password) or prompted -- never hard-coded.

The most useful go-live check: make a real Save in the live portal, then run
this. Your save should appear at the top of "MOST RECENT SAVES" with a fresh
timestamp and the values you entered.
"""
import ast
import getpass
import os
import sys

SCHEMA = os.environ.get("db_schema", "f4d")


def connect():
    import pytds
    user = os.environ.get("sql_username") or input("SQL username: ").strip()
    password = os.environ.get("sql_password") or getpass.getpass("SQL password: ")
    conn = pytds.connect(
        os.environ.get("sql_host", "WBGMSSQLEFIP001"),
        os.environ.get("sql_database", "WBG"), user, password,
        port=int(os.environ.get("sql_port", "5800")),
        autocommit=False, login_timeout=15)
    return conn


def scalar(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def is_blob(value):
    """True if the value is stored as a str(dict)/str(list) blob (deliverables,
    custom_indicators, operation_N, ...) rather than a plain scalar string
    (country, region_id, strategic_objective, ...)."""
    return bool(value) and value.lstrip()[:1] in "{["


def decode(value):
    """Parse a stored blob (str(dict)) safely; return (obj, error)."""
    if value is None:
        return None, "NULL"
    try:
        return ast.literal_eval(value), None
    except (ValueError, SyntaxError) as e:
        return None, f"UNPARSEABLE ({e})"


def overview(cur):
    S = SCHEMA
    print(f"\nConnected OK -> {os.environ.get('sql_host', 'WBGMSSQLEFIP001')}"
          f":{os.environ.get('sql_port', '5800')}  db={os.environ.get('sql_database', 'WBG')}"
          f"  schema={S}\n")

    trustfunds = scalar(cur, f"SELECT COUNT(*) FROM {S}.trustfunds WHERE deleted=0")
    users = scalar(cur, f"SELECT COUNT(*) FROM {S}.users WHERE deleted=0")
    total = scalar(cur, f"SELECT COUNT(*) FROM {S}.grant_info_long WHERE deleted=0")
    grants_with_data = scalar(
        cur, f"SELECT COUNT(DISTINCT trustfund_id) FROM {S}.grant_info_long WHERE deleted=0")
    print("REFERENCE DATA")
    print(f"  trust funds : {trustfunds}")
    print(f"  logins      : {users}")
    print("\nSUBMITTED DATA (grant_info_long)")
    print(f"  total rows           : {total}")
    print(f"  grants with >=1 save : {grants_with_data}")

    print("\n  by field (one grant fills several rows per section):")
    cur.execute(f"SELECT field, COUNT(*) FROM {S}.grant_info_long "
                f"WHERE deleted=0 GROUP BY field ORDER BY COUNT(*) DESC")
    for field, n in cur.fetchall():
        print(f"    {field:<28} {n}")

    # Latest saves -- the live "is it saving right now?" proof.
    N = 15
    print(f"\nMOST RECENT SAVES (top {N} by updated_at)")
    cur.execute(
        f"SELECT TOP ({N}) g.updated_at, t.name, f.fy, g.field, g.value "
        f"FROM {S}.grant_info_long g "
        f"LEFT JOIN {S}.trustfunds t ON t.id = g.trustfund_id "
        f"LEFT JOIN {S}.fys f ON f.id = g.fiscal_year_id "
        f"WHERE g.deleted=0 ORDER BY g.updated_at DESC")
    print(f"  {'updated_at':<20} {'grant':<26} {'fy':<8} {'field':<20} {'bytes':>7}")
    for ts, name, fy, field, value in cur.fetchall():
        size = len(value) if value else 0
        print(f"  {str(ts)[:19]:<20} {str(name)[:26]:<26} {str(fy or '-'):<8} "
              f"{field:<20} {size:>7}")

    # Confirm today's editable-unit change is actually persisting.
    print("\nSPOT CHECK: 'unit' key in recent Results Indicator saves")
    cur.execute(
        f"SELECT TOP (50) value FROM {S}.grant_info_long "
        f"WHERE deleted=0 AND field='custom_indicators' ORDER BY updated_at DESC")
    checked = with_unit = bad = 0
    for (value,) in cur.fetchall():
        obj, err = decode(value)
        if err:
            bad += 1
            continue
        checked += 1
        if isinstance(obj, dict) and any(
                isinstance(v, dict) and "unit" in v for v in obj.values()):
            with_unit += 1
    print(f"  parsed {checked} custom_indicators blobs "
          f"({bad} unparseable); {with_unit} contain a 'unit' value")

    # Integrity: every dict/list blob must round-trip through literal_eval.
    # Scalar-text rows (country, region_id, free text) are skipped -- they are
    # not Python literals and are not meant to parse.
    print("\nINTEGRITY: all dict/list blobs parse cleanly?")
    cur.execute(f"SELECT g.value, t.name, g.field FROM {S}.grant_info_long g "
                f"LEFT JOIN {S}.trustfunds t ON t.id=g.trustfund_id WHERE g.deleted=0")
    blobs = bad_rows = 0
    failures = []
    for value, name, field in cur.fetchall():
        if not is_blob(value):
            continue
        blobs += 1
        _, err = decode(value)
        if err:
            bad_rows += 1
            failures.append((name, field, err))
    if failures:
        print(f"  !! {bad_rows} of {blobs} blob(s) failed to parse:")
        for name, field, err in failures[:20]:
            print(f"     {name} / {field}: {err}")
    else:
        print(f"  OK -- all {blobs} dict/list blobs parse.")


def focus(cur, tf):
    S = SCHEMA
    print(f"\nFocus on grant matching '{tf}':\n")
    cur.execute(f"SELECT id, name, grant, ttl FROM {S}.trustfunds "
                f"WHERE deleted=0 AND name LIKE %s", ("%" + tf + "%",))
    matches = cur.fetchall()
    if not matches:
        print("  No trust fund whose name contains that text.")
        return
    for tid, name, grant, ttl in matches:
        print(f"  [{tid}] {name}   ttl={ttl or '-'}")
        print(f"        {grant or ''}")
        cur.execute(
            f"SELECT f.fy, g.field, g.updated_at, g.value "
            f"FROM {S}.grant_info_long g LEFT JOIN {S}.fys f ON f.id=g.fiscal_year_id "
            f"WHERE g.deleted=0 AND g.trustfund_id=%s ORDER BY f.fy, g.field", (tid,))
        rows = cur.fetchall()
        if not rows:
            print("        (no saved sections yet)\n")
            continue
        for fy, field, ts, value in rows:
            if is_blob(value):
                obj, err = decode(value)
                detail = ("[" + err + "]" if err
                          else f"{len(obj)} keys" if hasattr(obj, "__len__") else "ok")
            else:
                preview = (value or "").replace("\n", " ")
                detail = f'"{preview[:50]}"' + ("..." if len(preview) > 50 else "")
                obj = None
            print(f"        {str(fy or '-'):<8} {field:<20} saved {str(ts)[:19]}  {detail}")
            if field == "custom_indicators" and isinstance(obj, dict):
                for k, v in list(obj.items())[:6]:
                    if isinstance(v, dict):
                        print(f"            - {k}: value={v.get('input_value')!r} "
                              f"unit={v.get('unit')!r} target={v.get('target_value')!r}")
        print()


def main():
    conn = connect()
    cur = conn.cursor()
    try:
        if len(sys.argv) > 1:
            focus(cur, sys.argv[1].strip())
        else:
            overview(cur)
        print("\nDone. (read-only -- nothing was written)")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
