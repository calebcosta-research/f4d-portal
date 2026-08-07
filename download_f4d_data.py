"""Download all F4D Results Reporting data into a readable Excel workbook.

Read-only. Connects to the WB SQL Server, reads every grant's submissions, and
writes a single Excel file with clean, decoded sheets (Grant Info, Deliverables,
Results Indicators, and a complete Raw sheet). Nothing is written to the database.

Uses python-tds (``import pytds``) + openpyxl — the pure-Python tools that work on
the locked-down VDI and on a normal machine after a one-time
``pip install python-tds openpyxl``.

HOW TO RUN
  1. Make sure you can reach the WB database (on the WB network / VDI).
  2. Open a terminal in the folder that has this file.
  3. Run:   py download_f4d_data.py
     (on some machines the command is `python` instead of `py`)
  4. Type the database password when asked (Caleb will give it to you), Enter.
  5. When it finishes it prints the name of the Excel file it created, in this
     same folder. Open that file in Excel.

Server / database / port default to the known F4D values. The username defaults
to EFI_Admin. All can be overridden with environment variables (sql_host,
sql_database, sql_port, sql_username, sql_password) but you normally don't need to.
"""
import ast
import datetime
import getpass
import os
import sys

try:
    import pytds
except ImportError:
    sys.exit("Missing the database library. Run this once:  pip install python-tds openpyxl")
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
except ImportError:
    sys.exit("Missing openpyxl. Run this once:  pip install python-tds openpyxl")

SCHEMA = os.environ.get("db_schema", "f4d")


def connect():
    user = os.environ.get("sql_username", "EFI_Admin")
    password = os.environ.get("sql_password") or getpass.getpass(
        "Enter the database password (ask Caleb), then press Enter: ")
    print("Connecting to the database ...")
    return pytds.connect(
        os.environ.get("sql_host", "WBGMSSQLEFIP001"),
        os.environ.get("sql_database", "WBG"), user, password,
        port=int(os.environ.get("sql_port", "5800")),
        autocommit=False, login_timeout=30)


def decode(value):
    """Turn a stored blob (str(dict)) into a real dict; {} if it isn't one."""
    if isinstance(value, str) and value.lstrip()[:1] in "{[":
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return {}
    return {}


def main():
    conn = connect()
    cur = conn.cursor()

    # --- Look-up tables (id -> friendly text) ---------------------------------
    cur.execute(f"SELECT id, name, [grant], pcode, ttl, description FROM {SCHEMA}.trustfunds WHERE deleted=0")
    tf = {r[0]: {"name": r[1], "grant": r[2], "pcode": r[3], "ttl": r[4], "desc": r[5]}
          for r in cur.fetchall()}
    cur.execute(f"SELECT id, fy FROM {SCHEMA}.fys WHERE deleted=0")
    fy = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute(f"SELECT id, indicator_name, unit_of_measurement FROM {SCHEMA}.indicators")
    ind = {r[0]: {"name": r[1], "unit": r[2]} for r in cur.fetchall()}
    cur.execute(f"SELECT id, region FROM {SCHEMA}.regions")
    region = {str(r[0]): r[1] for r in cur.fetchall()}

    def gname(tid):
        g = tf.get(tid, {})
        return g.get("grant") or g.get("name") or f"TrustFund {tid}"

    def iname(key, blob_entry):
        # admin-mapped indicators are keyed by numeric id; TTL-added ones carry a name.
        if isinstance(blob_entry, dict) and blob_entry.get("name"):
            return blob_entry["name"]
        try:
            return ind.get(int(key), {}).get("name") or f"Indicator {key}"
        except (TypeError, ValueError):
            return f"Indicator {key}"

    # --- Read all submissions -------------------------------------------------
    print("Reading submissions ...")
    cur.execute(f"SELECT trustfund_id, fiscal_year_id, field, value, updated_at "
                f"FROM {SCHEMA}.grant_info_long WHERE deleted=0")
    rows = cur.fetchall()

    wb = Workbook()
    HEAD = PatternFill("solid", fgColor="1F4E79")
    hfont = Font(bold=True, color="FFFFFF")

    def new_sheet(title, headers):
        ws = wb.create_sheet(title)
        ws.append(headers)
        for c in range(1, len(headers) + 1):
            ws.cell(row=1, column=c).fill = HEAD
            ws.cell(row=1, column=c).font = hfont
            ws.cell(row=1, column=c).alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "A2"
        return ws

    wb.remove(wb.active)  # drop default sheet

    ws_info = new_sheet("Grant Info", [
        "Trust Fund #", "Grant Name", "TTL", "Fiscal Year", "Field", "Value"])
    ws_del = new_sheet("Deliverables", [
        "Trust Fund #", "Grant Name", "Fiscal Year", "Deliverable",
        "Progress / Status", "Target #", "Number Completed", "Description",
        "Next Steps", "Photos/Materials?"])
    ws_res = new_sheet("Results Indicators", [
        "Trust Fund #", "Grant Name", "Fiscal Year", "Indicator", "Unit",
        "Progress Value", "Explanation", "Baseline", "Baseline Yr",
        "Target", "Target Yr", "Level of Result", "Data Collection"])
    ws_raw = new_sheet("All Data (raw)", [
        "Trust Fund #", "Grant Name", "Fiscal Year", "Field", "Value", "Last Updated"])

    BLOB_FIELDS = {"deliverables", "custom_indicators"}

    for tid, fid, field, value, updated in rows:
        tfnum = tf.get(tid, {}).get("name", tid)
        grant = gname(tid)
        year = fy.get(fid, fid)

        # Raw catch-all (everything, unmodified)
        ws_raw.append([tfnum, grant, year, field, (value or "")[:32000],
                       str(updated)[:19] if updated else ""])

        if field == "deliverables":
            for key, d in decode(value).items():
                if not isinstance(d, dict) or d.get("archived"):
                    continue
                ws_del.append([tfnum, grant, year, iname(key, d),
                               d.get("input_value", ""), d.get("progress", ""),
                               d.get("deliverable_quantity", ""), d.get("description", ""),
                               d.get("next_steps", ""), d.get("supporting_materials_url", "")])
        elif field == "custom_indicators":
            for key, d in decode(value).items():
                if not isinstance(d, dict) or d.get("archived"):
                    continue
                ws_res.append([tfnum, grant, year, iname(key, d), d.get("unit", ""),
                               d.get("input_value", ""), d.get("progress", ""),
                               d.get("baseline_value", ""), d.get("year_baseline", ""),
                               d.get("target_value", ""), d.get("year_target", ""),
                               d.get("level_of_result", ""), d.get("data_collection", "")])
        elif field not in BLOB_FIELDS:
            # scalar / narrative fields -> readable Grant Info sheet
            shown = region.get(str(value), value) if field == "region_id" else value
            ws_info.append([tfnum, grant, tf.get(tid, {}).get("ttl", ""), year,
                            field, (str(shown) if shown is not None else "")[:32000]])

    # sensible column widths
    widths = {"Grant Info": [16, 40, 22, 10, 22, 60],
              "Deliverables": [14, 34, 10, 34, 18, 9, 15, 45, 35, 14],
              "Results Indicators": [14, 34, 10, 34, 10, 18, 40, 12, 10, 12, 10, 18, 22],
              "All Data (raw)": [14, 36, 10, 24, 70, 18]}
    for name, ws in [(s.title, s) for s in wb.worksheets]:
        for i, w in enumerate(widths.get(name, []), start=1):
            ws.column_dimensions[chr(64 + i)].width = w

    ts = datetime.datetime.now().strftime("%Y-%m-%d")
    out = os.path.abspath(f"F4D_data_export_{ts}.xlsx")
    wb.save(out)
    cur.close()
    conn.close()

    print("\nDONE. Excel file created:")
    print("   " + out)
    print(f"\nSheets: Grant Info ({ws_info.max_row - 1} rows), "
          f"Deliverables ({ws_del.max_row - 1}), "
          f"Results Indicators ({ws_res.max_row - 1}), "
          f"All Data raw ({ws_raw.max_row - 1}).")
    print("Open that file in Excel. (Read-only — nothing in the database changed.)")


if __name__ == "__main__":
    main()
