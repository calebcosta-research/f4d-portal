"""Export the live F4D database to SQL files for loading into Azure SQL.

This runs on the WB VDI, which blocks compiled Python extensions by group
policy -- so it uses pytds (pure Python) and the standard library only. No
pandas, no pyodbc, no pymssql.

It reads WBG.f4d read-only and writes numbered .sql files that recreate every
row in a fresh database. Primary keys are preserved (via IDENTITY_INSERT) so
the foreign keys between tables stay valid.

The output works either way you choose to load it: pasted into the Azure portal
Query editor, or replayed by a script over a direct connection.

Install the driver once:

    py -m pip install python-tds

Run (PowerShell on the VDI):

    $env:sql_username = "EFI_Admin"
    $env:sql_password = "<password>"
    py export_live_to_sql.py

Files land in .\f4d_export\ -- run them in filename order.
"""
import datetime
import decimal
import os
import sys

try:
    import pytds
except ImportError:
    sys.exit("python-tds is not installed. Run:  py -m pip install python-tds")


# --- Source: the live database, reachable only from the VDI ----------------
HOST = os.environ.get("sql_host", "WBGMSSQLEFIP001")
PORT = int(os.environ.get("sql_port", "5800"))
DATABASE = os.environ.get("sql_database", "WBG")
SRC_SCHEMA = os.environ.get("src_schema", "f4d")
USER = os.environ.get("sql_username")
PASSWORD = os.environ.get("sql_password")

# --- Target: schema the INSERTs will be written against --------------------
DST_SCHEMA = os.environ.get("dst_schema", "dbo")

OUT_DIR = os.environ.get("out_dir", "f4d_export")

# Parent tables first, so foreign keys always resolve on load.
TABLES = [
    "teams",
    "fys",
    "regions",
    "countries",
    "users",
    "trustfunds",
    "indicators",
    "trustfund_indicator_mapping",
    "grant_info_long",
]

# Multi-row INSERT batches. SQL Server caps a VALUES list at 1000 rows; 200
# keeps individual statements small enough for the portal's Query editor.
ROWS_PER_INSERT = 200
# Roughly the largest file worth pasting into a browser editor in one go.
MAX_FILE_BYTES = 700_000


def sql_literal(v):
    """Render a Python value as a T-SQL literal."""
    if v is None:
        return "NULL"
    # bool before int -- bool is a subclass of int.
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, datetime.datetime):
        return "'" + v.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "'"
    if isinstance(v, datetime.date):
        return "'" + v.isoformat() + "'"
    if isinstance(v, datetime.time):
        return "'" + v.isoformat() + "'"
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    # N'' so unicode survives; double up embedded quotes.
    return "N'" + str(v).replace("'", "''") + "'"


def columns_of(cur, table):
    """Column names in ordinal order, and whether the table has an identity."""
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
        "ORDER BY ORDINAL_POSITION",
        (SRC_SCHEMA, table),
    )
    cols = [r[0] for r in cur.fetchall()]

    cur.execute(
        "SELECT COUNT(*) FROM sys.identity_columns "
        "WHERE object_id = OBJECT_ID(%s)",
        (f"{SRC_SCHEMA}.{table}",),
    )
    has_identity = cur.fetchone()[0] > 0
    return cols, has_identity


def write_table(cur, table, index):
    """Dump one table to one or more .sql files. Returns the row count."""
    cols, has_identity = columns_of(cur, table)
    if not cols:
        print("  %-30s SKIPPED (not found in source)" % table)
        return 0

    col_list = ", ".join("[%s]" % c for c in cols)
    cur.execute("SELECT %s FROM [%s].[%s]" % (col_list, SRC_SCHEMA, table))

    target = "[%s].[%s]" % (DST_SCHEMA, table)
    header = "SET IDENTITY_INSERT %s ON;\n" % target if has_identity else ""
    footer = "SET IDENTITY_INSERT %s OFF;\n" % target if has_identity else ""

    total = 0
    part = 1
    handle = None
    written = 0

    def open_part():
        nonlocal handle, written
        name = "%02d_%s_%02d.sql" % (index, table, part)
        handle = open(os.path.join(OUT_DIR, name), "w", encoding="utf-8")
        handle.write("-- %s -> %s (part %d)\n" % (table, target, part))
        handle.write(header)
        written = len(header)

    def close_part():
        if handle:
            handle.write(footer)
            handle.close()

    while True:
        batch = cur.fetchmany(ROWS_PER_INSERT)
        if not batch:
            break
        if handle is None:
            open_part()

        values = ",\n".join(
            "  (" + ", ".join(sql_literal(v) for v in row) + ")" for row in batch
        )
        stmt = "INSERT INTO %s (%s) VALUES\n%s;\n" % (target, col_list, values)
        handle.write(stmt)
        written += len(stmt)
        total += len(batch)

        # Roll to a new file once this one gets unwieldy.
        if written >= MAX_FILE_BYTES:
            close_part()
            handle = None
            part += 1

    close_part()

    if total == 0:
        # Still leave a marker, so a missing file never looks like a lost table.
        with open(os.path.join(OUT_DIR, "%02d_%s_empty.sql" % (index, table)),
                  "w", encoding="utf-8") as fh:
            fh.write("-- %s had no rows in the source database\n" % table)

    print("  %-30s %7d rows -> %d file(s)" % (table, total, part if total else 0))
    return total


def main():
    if not USER or not PASSWORD:
        sys.exit("Set sql_username and sql_password first:\n"
                 '  $env:sql_username = "EFI_Admin"\n'
                 '  $env:sql_password = "<password>"')

    os.makedirs(OUT_DIR, exist_ok=True)

    print("Reading %s:%s/%s schema [%s]" % (HOST, PORT, DATABASE, SRC_SCHEMA))
    print("Writing INSERTs targeting schema [%s] into .\\%s\\\n"
          % (DST_SCHEMA, OUT_DIR))

    conn = pytds.connect(server=HOST, port=PORT, database=DATABASE,
                         user=USER, password=PASSWORD, login_timeout=30)
    counts = {}
    try:
        with conn.cursor() as cur:
            for i, table in enumerate(TABLES, start=1):
                counts[table] = write_table(cur, table, i)
    finally:
        conn.close()

    # A verification script to run against Azure after loading.
    with open(os.path.join(OUT_DIR, "99_verify.sql"), "w", encoding="utf-8") as fh:
        fh.write("-- Run this on Azure after loading. Every row should match\n")
        fh.write("-- the 'expected' column, which is what the source held.\n")
        fh.write("\nUNION ALL\n".join(
            "SELECT '%s' AS table_name, %d AS expected, "
            "(SELECT COUNT(*) FROM [%s].[%s]) AS loaded"
            % (t, counts.get(t, 0), DST_SCHEMA, t) for t in TABLES
        ))
        fh.write(";\n")

    print("\nTotal rows: %d" % sum(counts.values()))
    print("Files are in .\\%s\\ -- run them in filename order." % OUT_DIR)
    print("99_verify.sql checks the load afterwards.")


if __name__ == "__main__":
    main()
