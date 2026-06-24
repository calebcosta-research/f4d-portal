"""Analyst-friendly Excel export of all submissions, auto-uploaded to Azure Blob.

Builds one workbook with three sheets:
  * Trust Funds  — one row per trust fund, submission status per fiscal year
                   (Not Started / In Progress / Submitted).
  * Deliverables — one row per deliverable (flattened, names not IDs).
  * Results      — one row per results indicator (flattened).

`export_report_safe()` runs the build+upload in a daemon thread so a TTL's Save
or Submit returns immediately and the blob refreshes a moment later. It is
best-effort: any failure (e.g. blob not configured locally) is swallowed.
"""
import ast
import io
import os
import threading
from collections import defaultdict

import pandas as pd

from connection import create_session
from model import GrantInfo, TrustFund, FiscalYear, Indicator

CONTAINER = os.environ.get("F4D_EXPORT_CONTAINER", "exports")
BLOB_NAME = os.environ.get("F4D_EXPORT_BLOB", "f4d_all_submissions.xlsx")
_STATUS_META = {"report_status", "report_submitted_at"}


def _parse_blob(value):
    if not value:
        return {}
    try:
        data = ast.literal_eval(value)
        return data if isinstance(data, dict) else {}
    except (ValueError, SyntaxError):
        return {}


def _indicator_meta(indicators, key):
    """(display name, standard indicator, unit) for a blob key (PK or custom_*)."""
    if str(key).isdigit() and int(key) in indicators:
        ind = indicators[int(key)]
        return ind.indicator_name, (ind.standard_indicator_name or ""), (ind.unit_of_measurement or "")
    return str(key), "", ""


def build_report_bytes(session=None):
    own = session is None
    if own:
        session = create_session()
    try:
        indicators = {i.id: i for i in session.query(Indicator).all()}
        tfs = {t.id: t for t in session.query(TrustFund).filter(
            TrustFund.project_type == "Trust Fund", TrustFund.deleted == False).all()}
        fys = {f.id: f.fy for f in session.query(FiscalYear).filter(
            FiscalYear.deleted == False).all()}
        fy_labels = [fys[k] for k in sorted(fys, key=lambda k: fys[k])]

        grouped = defaultdict(dict)  # (tf_id, fy_id) -> {field: value}
        for r in session.query(GrantInfo).filter(GrantInfo.deleted == False).all():
            grouped[(r.trustfund_id, r.fiscal_year_id)][r.field] = r.value

        deliv_rows, res_rows = [], []
        status_map = defaultdict(dict)  # tf_id -> {fy_label: status}

        for (tf_id, fy_id), fields in grouped.items():
            tf = tfs.get(tf_id)
            if not tf:
                continue
            fy = fys.get(fy_id, "")
            gnum = tf.grant or tf.name
            gname = tf.description or ""

            if fields.get("report_status") == "submitted":
                status = "Submitted"
            elif any(k not in _STATUS_META for k in fields):
                status = "In Progress"
            else:
                status = "Not Started"
            if fy:
                status_map[tf_id][fy] = status

            for key, e in _parse_blob(fields.get("deliverables")).items():
                if not isinstance(e, dict):
                    continue
                name = e.get("name") if str(key).startswith("custom_") else _indicator_meta(indicators, key)[0]
                std = _indicator_meta(indicators, key)[1]
                deliv_rows.append({
                    "Trust Fund": gnum, "Grant Name": gname, "Fiscal Year": fy,
                    "Deliverable": name, "Standard Indicator": std,
                    "Status": e.get("input_value", ""),
                    "Target Number of Deliverables": e.get("progress", ""),
                    "Number In Progress/Completed": e.get("deliverable_quantity", ""),
                    "Description": e.get("description", ""),
                    "Data Source": e.get("data_source", ""),
                    "Has Media": e.get("supporting_materials_url", ""),
                    "Next Steps": e.get("next_steps", ""),
                    "Archived": bool(e.get("archived", False)),
                })

            for key, e in _parse_blob(fields.get("custom_indicators")).items():
                if not isinstance(e, dict):
                    continue
                name, std, unit = _indicator_meta(indicators, key)
                if str(key).startswith("custom_"):
                    name = e.get("name") or name
                res_rows.append({
                    "Trust Fund": gnum, "Grant Name": gname, "Fiscal Year": fy,
                    "Indicator": name, "Standard Indicator": std, "Unit": unit,
                    "Value": e.get("input_value", ""),
                    "Baseline": e.get("baseline_value", ""),
                    "Target": e.get("target_value", ""),
                    "Level of Result": e.get("level_of_result", ""),
                    "Data Collection": e.get("data_collection", ""),
                    "Archived": bool(e.get("archived", False)),
                })

        status_rows = []
        for tf_id, tf in sorted(tfs.items(), key=lambda kv: (kv[1].grant or kv[1].name or "")):
            row = {"Trust Fund": tf.grant or tf.name, "Grant Name": tf.description or "",
                   "P-code": tf.pcode or "", "TTL": tf.ttl or ""}
            for fyl in fy_labels:
                row[fyl] = status_map.get(tf_id, {}).get(fyl, "Not Started")
            status_rows.append(row)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            (pd.DataFrame(status_rows) if status_rows else pd.DataFrame(
                columns=["Trust Fund", "Grant Name", "P-code", "TTL"] + fy_labels)
             ).to_excel(xw, sheet_name="Trust Funds", index=False)
            (pd.DataFrame(deliv_rows) if deliv_rows else pd.DataFrame(
                columns=["Trust Fund", "Grant Name", "Fiscal Year", "Deliverable"])
             ).to_excel(xw, sheet_name="Deliverables", index=False)
            (pd.DataFrame(res_rows) if res_rows else pd.DataFrame(
                columns=["Trust Fund", "Grant Name", "Fiscal Year", "Indicator"])
             ).to_excel(xw, sheet_name="Results", index=False)
        return buf.getvalue()
    finally:
        if own:
            session.close()


def upload_report(data):
    """Upload the workbook to Azure Blob. Returns True/False. No-op if unset."""
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        return False
    from azure.storage.blob import BlobServiceClient, ContentSettings
    client = BlobServiceClient.from_connection_string(conn).get_blob_client(
        container=CONTAINER, blob=BLOB_NAME)
    client.upload_blob(
        data, overwrite=True,
        content_settings=ContentSettings(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
    return True


def _run():
    try:
        upload_report(build_report_bytes())
    except Exception:  # noqa: BLE001 - never break a save/submit
        pass


def export_report_safe():
    """Fire-and-forget: rebuild + upload the report in a background thread."""
    threading.Thread(target=_run, daemon=True).start()
