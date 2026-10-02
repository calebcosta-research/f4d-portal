"""Drop one or more grants from the portal (and so from the data download).

A soft delete, the same one superadmin's "Delete" button does, extended to
everything that belongs to the grant:
  * the trust fund row                      (trustfunds.deleted = 1)
  * its login, <TF number>_admin             (users.deleted = 1 -- needs the
    login fix in f4d/auth.py live on Connect before it actually stops sign-in)
  * its saved answers, every fiscal year     (grant_info_long.deleted = 1)
  * its indicator mappings                   (trustfund_indicator_mapping.deleted = 1)
Nothing is removed from the database, so a drop can be undone: the backup file
it writes lists every row id it changed, with the SQL to flip them back.

Safe by design, like clear_test_submission_pytds.py:
  * the grant must match EXACTLY (TF0C2833 never catches TF0C28331);
  * DRY-RUN by default -- shows what would be dropped, changes nothing;
  * shows each grant's saved answers first, so data entered under the wrong
    number can be rescued before it's hidden;
  * other logins on the same team are listed but never touched;
  * requires typing the grant numbers to confirm.

    $env:sql_username="EFI_Admin"; $env:sql_password="<password>"

    py drop_trust_fund_pytds.py TF0C2833 TF0C5019           # DRY RUN
    py drop_trust_fund_pytds.py TF0C2833 TF0C5019 --drop    # actually drop

Env overrides: sql_host, sql_database, sql_port, db_schema.
"""
import datetime
import getpass
import os
import sys

SCHEMA = os.environ.get("db_schema", "f4d")


def connect():
    import pytds
    user = os.environ.get("sql_username") or input("SQL username: ").strip()
    password = os.environ.get("sql_password") or getpass.getpass("SQL password: ")
    return pytds.connect(
        os.environ.get("sql_host", "WBGMSSQLEFIP001"),
        os.environ.get("sql_database", "WBG"), user, password,
        port=int(os.environ.get("sql_port", "5800")),
        autocommit=False, login_timeout=30)


def ids(cur, sql, params):
    cur.execute(sql, params)
    return [r[0] for r in cur.fetchall()]


def find(cur, grant):
    """Everything to drop for one grant number, or None if it isn't there."""
    S = SCHEMA
    login = f"{grant}_admin"
    # The login name is the trust fund's name; the number itself is in [grant].
    cur.execute(f"SELECT id, name, [grant], ttl, team_id FROM {S}.trustfunds "
                f"WHERE deleted=0 AND (UPPER(name)=UPPER(%s) OR UPPER([grant])=UPPER(%s))",
                (login, grant))
    funds = cur.fetchall()
    if not funds:
        return None
    fund_ids = [f[0] for f in funds]
    ph = ",".join(["%s"] * len(fund_ids))
    names = [f[1] for f in funds] + [login]
    nph = ",".join(["%s"] * len(names))
    cur.execute(f"SELECT f.fy, g.field, g.updated_at FROM {S}.grant_info_long g "
                f"LEFT JOIN {S}.fys f ON f.id=g.fiscal_year_id "
                f"WHERE g.deleted=0 AND g.trustfund_id IN ({ph}) ORDER BY f.fy, g.field",
                tuple(fund_ids))
    saved = cur.fetchall()
    team_ids = sorted({f[4] for f in funds if f[4] is not None})
    others = []
    if team_ids:
        tph = ",".join(["%s"] * len(team_ids))
        cur.execute(f"SELECT username FROM {S}.users WHERE deleted=0 "
                    f"AND team_id IN ({tph}) AND username NOT IN ({nph})",
                    tuple(team_ids) + tuple(names))
        others = [r[0] for r in cur.fetchall()]
    return {
        "funds": funds,
        "trustfunds": fund_ids,
        "users": ids(cur, f"SELECT id FROM {S}.users WHERE deleted=0 "
                          f"AND username IN ({nph})", tuple(names)),
        "grant_info_long": ids(cur, f"SELECT id FROM {S}.grant_info_long "
                                    f"WHERE deleted=0 AND trustfund_id IN ({ph})",
                               tuple(fund_ids)),
        "trustfund_indicator_mapping": ids(
            cur, f"SELECT id FROM {S}.trustfund_indicator_mapping "
                 f"WHERE deleted=0 AND trustfund_id IN ({ph})", tuple(fund_ids)),
        "saved": saved,
        "other_logins": others,
    }


TABLES = ["grant_info_long", "trustfund_indicator_mapping", "users", "trustfunds"]


def main():
    args = [a for a in sys.argv[1:] if a != "--drop"]
    do_drop = "--drop" in sys.argv[1:]
    grants = [a.strip().upper() for a in args if a.strip()]
    if not grants:
        print("Usage: py drop_trust_fund_pytds.py <TFnumber> [<TFnumber> ...] [--drop]")
        sys.exit(1)

    S = SCHEMA
    conn = connect()
    cur = conn.cursor()
    try:
        plan = {}
        for grant in grants:
            found = find(cur, grant)
            print("")
            if not found:
                print(f"{grant}: no active trust fund with that number "
                      "(already dropped, or mistyped). Skipped.")
                continue
            plan[grant] = found
            for tid, name, number, ttl, team_id in found["funds"]:
                print(f"{grant}: trust fund [{tid}] {name}  grant={number}  "
                      f"ttl={ttl or '-'}  team={team_id}")
            print(f"   logins to drop      : {len(found['users'])}")
            print(f"   indicator mappings  : {len(found['trustfund_indicator_mapping'])}")
            print(f"   saved answers       : {len(found['grant_info_long'])}")
            for fy, field, ts in found["saved"]:
                print(f"      {str(fy or '-'):<6} {field:<28} saved {str(ts)[:19]}")
            if found["saved"]:
                print("   !! This grant has saved answers. If a TTL entered them here by "
                      "mistake, rescue them before dropping.")
            if found["other_logins"]:
                print("   Other logins on the same team (NOT touched): "
                      + ", ".join(found["other_logins"]))

        if not plan:
            print("\nNothing to drop.")
            return
        if not do_drop:
            print("\nDRY RUN -- nothing was changed.")
            print("Re-run with --drop to drop: "
                  f"py drop_trust_fund_pytds.py {' '.join(plan)} --drop")
            return

        # Backup first: every id about to change, and how to undo it.
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"dropped_{'_'.join(plan)}_{ts}.txt"
        with open(backup, "w", encoding="utf-8") as fh:
            fh.write(f"# Grants dropped {ts}: {', '.join(plan)}\n")
            fh.write("# To undo, run these statements:\n")
            for grant, found in plan.items():
                for table in TABLES:
                    if found[table]:
                        fh.write(f"UPDATE {S}.{table} SET deleted=0 WHERE id IN "
                                 f"({', '.join(str(i) for i in found[table])});  -- {grant}\n")
        print(f"\nBackup / undo file written: {os.path.abspath(backup)}")

        typed = input(f'\nType  {" ".join(plan)}  to drop these grant(s): ').strip().upper()
        if typed.split() != list(plan):
            print("Confirmation did not match. Aborted -- nothing changed.")
            return

        now = datetime.datetime.now()
        for grant, found in plan.items():
            for table in TABLES:
                if found[table]:
                    ph = ",".join(["%s"] * len(found[table]))
                    cur.execute(f"UPDATE {S}.{table} SET deleted=1, updated_at=%s "
                                f"WHERE id IN ({ph})", (now,) + tuple(found[table]))
        conn.commit()
        print(f"Dropped {', '.join(plan)} and committed. They are left out of "
              "download_f4d_data.py's export from now on.")
        print(f"Undo: run the statements in {backup}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
