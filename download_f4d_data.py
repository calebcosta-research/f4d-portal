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

    # Per-(grant, fiscal year) context so each Deliverables / Results row can
    # carry the grant's inputs (country, region, pillars, etc.) as own columns.
    CONTEXT = [
        ("country", "Country"), ("region_id", "Region"),
        ("p_code_instrument", "Product Line"), ("f4d_association", "F4D Association"),
        ("pillars", "Pillars"), ("ccts", "Cross-Cutting Themes"),
        ("strategic_objective", "Strategic Objective"),
    ]
    ctx_headers = [name for _, name in CONTEXT]
    ctx_fields = {f for f, _ in CONTEXT}
    context = {}
    for _tid, _fid, _field, _value, _upd in rows:
        if _field in ctx_fields:
            _v = region.get(str(_value), _value) if _field == "region_id" else _value
            context.setdefault((_tid, _fid), {})[_field] = "" if _v is None else _v

    def prefix(tid, fid):
        c = context.get((tid, fid), {})
        return ([tf.get(tid, {}).get("name", tid), gname(tid),
                 tf.get(tid, {}).get("ttl", ""), fy.get(fid, fid)]
                + [c.get(f, "") for f, _ in CONTEXT])

    # Per-grant progress for the current reporting year (the newest fiscal year):
    # Not Started = no data for it, In Progress = saved but not submitted,
    # Complete = a submission was recorded (report_submitted_at / report_status).
    newest_fy = max(fy.keys()) if fy else None
    prog = {}
    for _tid, _fid, _field, _value, _upd in rows:
        if _fid != newest_fy:
            continue
        p = prog.setdefault(_tid, {"last": None, "submitted_at": "", "complete": False})
        if _upd and (p["last"] is None or _upd > p["last"]):
            p["last"] = _upd
        if _field == "report_submitted_at" and _value:
            p["submitted_at"], p["complete"] = _value, True
        elif _field == "report_status" and _value:
            p["complete"] = True

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

    # Project Progress — one row per grant, at-a-glance status for the reporting year.
    ws_prog = new_sheet("Project Progress",
        ["Trust Fund #", "Grant Name", "TTL", "Status", "Last Updated", "Submitted At"])
    for _tid, _meta in sorted(tf.items(), key=lambda kv: (kv[1].get("name") or "")):
        p = prog.get(_tid)
        if not p:
            ws_prog.append([_meta.get("name"), gname(_tid), _meta.get("ttl", ""),
                            "Not Started", "", ""])
        else:
            ws_prog.append([_meta.get("name"), gname(_tid), _meta.get("ttl", ""),
                            "Complete" if p["complete"] else "In Progress",
                            str(p["last"])[:19] if p["last"] else "", p["submitted_at"]])

    ws_info = new_sheet("Grant Info", [
        "Trust Fund #", "Grant Name", "TTL", "Fiscal Year", "Field", "Value"])
    ws_del = new_sheet("Deliverables",
        ["Trust Fund #", "Grant Name", "TTL", "Fiscal Year"] + ctx_headers +
        ["Deliverable", "Progress / Status", "Target #", "Number Completed",
         "Description", "Next Steps", "Photos/Materials?"])
    ws_res = new_sheet("Results Indicators",
        ["Trust Fund #", "Grant Name", "TTL", "Fiscal Year"] + ctx_headers +
        ["Indicator", "Unit", "Progress Value", "Explanation", "Baseline",
         "Baseline Yr", "Target", "Target Yr", "Level of Result", "Data Collection"])
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
                ws_del.append(prefix(tid, fid) + [
                    iname(key, d), d.get("input_value", ""), d.get("progress", ""),
                    d.get("deliverable_quantity", ""), d.get("description", ""),
                    d.get("next_steps", ""), d.get("supporting_materials_url", "")])
        elif field == "custom_indicators":
            for key, d in decode(value).items():
                if not isinstance(d, dict) or d.get("archived"):
                    continue
                ws_res.append(prefix(tid, fid) + [
                    iname(key, d), d.get("unit", ""), d.get("input_value", ""),
                    d.get("progress", ""), d.get("baseline_value", ""),
                    d.get("year_baseline", ""), d.get("target_value", ""),
                    d.get("year_target", ""), d.get("level_of_result", ""),
                    d.get("data_collection", "")])
        elif field not in BLOB_FIELDS:
            # scalar / narrative fields -> readable Grant Info sheet
            shown = region.get(str(value), value) if field == "region_id" else value
            ws_info.append([tfnum, grant, tf.get(tid, {}).get("ttl", ""), year,
                            field, (str(shown) if shown is not None else "")[:32000]])

    # column widths by header name (robust to the added context columns)
    WIDE = {"Grant Name": 34, "TTL": 20, "Strategic Objective": 48, "Description": 45,
            "Next Steps": 34, "Explanation": 40, "Deliverable": 34, "Indicator": 34,
            "Pillars": 30, "Cross-Cutting Themes": 28, "F4D Association": 28,
            "Country": 18, "Region": 22, "Product Line": 14, "Data Collection": 22,
            "Value": 60, "Field": 22, "Status": 13, "Last Updated": 20, "Submitted At": 20}
    for ws in wb.worksheets:
        for cell in ws[1]:
            ws.column_dimensions[cell.column_letter].width = WIDE.get(cell.value, 14)

    ts = datetime.datetime.now().strftime("%Y-%m-%d")
    out = os.path.abspath(f"F4D_data_export_{ts}.xlsx")
    wb.save(out)
    cur.close()
    conn.close()

    print("\nDONE. Excel file created:")
    print("   " + out)
    print(f"\nSheets: Project Progress ({ws_prog.max_row - 1} grants), "
          f"Grant Info ({ws_info.max_row - 1} rows), "
          f"Deliverables ({ws_del.max_row - 1}), "
          f"Results Indicators ({ws_res.max_row - 1}), "
          f"All Data raw ({ws_raw.max_row - 1}).")
    print("Open that file in Excel. (Read-only — nothing in the database changed.)")


if __name__ == "__main__":
    main()
