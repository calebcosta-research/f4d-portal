"""Master CSV of all grant submissions.

Pivots the EAV grant_info_long table into one row per (trust fund x fiscal year),
adds trust-fund metadata and submission status, and writes it to
exports/all_submissions.csv. Regenerated on each report submission so the file
always reflects the current state of every grant — this replaces the old
per-TTL "Download results" page.

Pure module (no Streamlit): callable from the app or a cron/script. Blob fields
(deliverables, custom_indicators, operation_N, collaboration_N, ...) are written
as their stored string so no information is lost.
"""
import os
import tempfile

import pandas as pd

from connection import create_session
from model import GrantInfo, TrustFund, FiscalYear

# exports/all_submissions.csv at the project root (sibling of the f4d package).
DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "all_submissions.csv",
)

# Columns surfaced first; everything else (the EAV fields) follows, sorted.
META_COLS = ["trust_fund", "grant_number", "pcode", "ttl", "fiscal_year",
             "report_status", "report_submitted_at"]


def write_master_csv(out_path=None, session=None):
    """Write the master CSV. Returns (path, row_count). Atomic (temp + rename)."""
    out_path = out_path or DEFAULT_OUT
    own_session = session is None
    if own_session:
        session = create_session()
    try:
        records = (
            session.query(GrantInfo, TrustFund, FiscalYear)
            .join(TrustFund, GrantInfo.trustfund_id == TrustFund.id)
            .outerjoin(FiscalYear, GrantInfo.fiscal_year_id == FiscalYear.id)
            .filter(GrantInfo.deleted == False)
            .all()
        )

        # One row per (trust fund, fiscal year); each field becomes a column.
        grouped = {}
        for gi, tf, fy in records:
            key = (tf.id, gi.fiscal_year_id)
            row = grouped.get(key)
            if row is None:
                row = {
                    "trust_fund": tf.name, "grant_number": tf.grant,
                    "pcode": tf.pcode, "ttl": tf.ttl,
                    "fiscal_year": fy.fy if fy else "",
                }
                grouped[key] = row
            row[gi.field] = gi.value

        rows = list(grouped.values())
        field_cols = sorted({k for r in rows for k in r} - set(META_COLS))
        df = pd.DataFrame(rows, columns=META_COLS + field_cols)

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(out_path), suffix=".tmp")
        os.close(fd)
        df.to_csv(tmp, index=False)
        os.replace(tmp, out_path)  # atomic on the same filesystem
        return out_path, len(rows)
    finally:
        if own_session:
            session.close()


if __name__ == "__main__":
    path, n = write_master_csv()
    print(f"Wrote {n} grant-year rows to {path}")
