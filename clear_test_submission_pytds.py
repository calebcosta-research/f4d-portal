"""Delete ONE grant's submission for a given fiscal year (test-data cleanup).

Scoped and safe by design:
  * targets a single grant (matched by trust-fund number / login name) AND a
    single fiscal year -- never a blanket wipe, so a real TTL submitting under a
    different grant can't be caught in it;
  * DRY-RUN by default -- shows every row it would delete, changes nothing;
  * writes a restorable BACKUP file of those rows before deleting;
  * requires you to type the grant number to confirm.

Uses python-tds (``import pytds``), the pure-Python driver that imports under the
VDI's group-policy DLL block.

    $env:sql_username="EFI_Admin"; $env:sql_password="<password>"

    py clear_test_submission_pytds.py TF0D2299             # DRY RUN (FY26)
    py clear_test_submission_pytds.py TF0D2299 --delete    # actually delete
    py clear_test_submission_pytds.py TF0D2299 FY25 --delete   # a different FY

Env overrides: sql_host, sql_database, sql_port, db_schema. FY defaults to FY26.
"""
import datetime
import getpass
import os
import sys

SCHEMA = os.environ.get("db_schema", "f4d")
COLUMNS = ["id", "trustfund_id", "fiscal_year_id", "field", "value",
           "team_id", "deleted", "created_at", "updated_at"]


def connect():
    import pytds
    user = os.environ.get("sql_username") or input("SQL username: ").strip()
    password = os.environ.get("sql_password") or getpass.getpass("SQL password: ")
    return pytds.connect(
        os.environ.get("sql_host", "WBGMSSQLEFIP001"),
        os.environ.get("sql_database", "WBG"), user, password,
        port=int(os.environ.get("sql_port", "5800")),
        autocommit=False, login_timeout=30)


def parse_args(argv):
    grant = fy = None
    do_delete = False
    for a in argv:
        if a == "--delete":
            do_delete = True
        elif a.upper().startswith("FY"):
            fy = a
        elif grant is None:
            grant = a
    return grant, (fy or "FY26"), do_delete


def main():
    grant, fy, do_delete = parse_args(sys.argv[1:])
    if not grant:
        print("Usage: py clear_test_submission_pytds.py <TFnumber> [FYxx] [--delete]")
        sys.exit(1)
    S = SCHEMA

    conn = connect()
    cur = conn.cursor()
    try:
        # Resolve the grant(s) by name (TrustFund.name == login username).
        cur.execute(f"SELECT id, name FROM {S}.trustfunds "
                    f"WHERE deleted=0 AND name LIKE %s", ("%" + grant + "%",))
        tfs = cur.fetchall()
        if not tfs:
            print(f"No trust fund whose name contains '{grant}'. Nothing to do.")
            return
        print(f"\nMatched grant(s) for '{grant}':")
        for tid, name in tfs:
            print(f"  [{tid}] {name}")
        tf_ids = [t[0] for t in tfs]

        # Resolve the fiscal year.
        cur.execute(f"SELECT id, fy FROM {S}.fys WHERE fy=%s AND deleted=0", (fy,))
        fys = cur.fetchall()
        if not fys:
            print(f"\nNo fiscal year '{fy}'. Nothing to do.")
            return
        fy_ids = [f[0] for f in fys]
        print(f"Fiscal year: {fy} (id {', '.join(str(i) for i in fy_ids)})")

        tf_ph = ",".join(["%s"] * len(tf_ids))
        fy_ph = ",".join(["%s"] * len(fy_ids))
        where = f"trustfund_id IN ({tf_ph}) AND fiscal_year_id IN ({fy_ph})"
        params = tuple(tf_ids) + tuple(fy_ids)

        # Fetch the exact rows in scope.
        cur.execute(f"SELECT {', '.join(COLUMNS)} FROM {S}.grant_info_long "
                    f"WHERE {where} ORDER BY field", params)
        rows = cur.fetchall()

        print(f"\nRows to delete: {len(rows)}")
        if not rows:
            print("Nothing matches. Done.")
            return
        for r in rows:
            d = dict(zip(COLUMNS, r))
            size = len(d["value"]) if d["value"] else 0
            print(f"  {d['field']:<28} {size:>6} bytes   saved {str(d['updated_at'])[:19]}")

        if not do_delete:
            print("\nDRY RUN -- nothing was deleted.")
            print(f"Re-run with --delete to remove these {len(rows)} row(s):")
            print(f"  py clear_test_submission_pytds.py {grant} {fy} --delete")
            return

        # Backup first -- restorable record of everything about to go.
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"deleted_{grant}_{fy}_{ts}.bak"
        with open(backup, "w", encoding="utf-8") as fh:
            fh.write(f"# backup of {len(rows)} grant_info_long rows "
                     f"({grant} / {fy}) taken {ts}\n")
            fh.write(f"# columns: {COLUMNS}\n")
            for r in rows:
                fh.write(repr(dict(zip(COLUMNS, r))) + "\n")
        print(f"\nBackup written: {os.path.abspath(backup)}")

        # Typed confirmation.
        typed = input(f'\nType the grant number "{grant}" to permanently delete '
                      f'these {len(rows)} row(s): ').strip()
        if typed != grant:
            print("Confirmation did not match. Aborted -- nothing deleted.")
            return

        cur.execute(f"DELETE FROM {S}.grant_info_long WHERE {where}", params)
        deleted = cur.rowcount
        conn.commit()
        print(f"Deleted {deleted} row(s) and committed. "
              f"({grant} {fy} is now clear; backup at {backup})")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
