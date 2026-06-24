"""Review & Submit — the final report step.

Per-section "Save" persists work in progress; this page validates the whole
report's mandatory fields (from saved data) and, when complete, stamps it
submitted with a timestamp. Light version: it records status only — it does not
lock editing or notify anyone (those can be layered on later).
"""
import datetime

import streamlit as st
from connection import create_session
from f4d.data_access import get_long_format_value, update_long_format_field
from f4d.validation import validate_report, report_is_complete
from f4d.reporting_export import export_report_safe


def review_submit():
    st.success("### 7. Review & Submit")

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

    tf_id = st.session_state.current_trustfund_id
    fy_id = st.session_state.current_fiscal_year_id
    if not tf_id:
        st.error("No grant selected. Open **Basic Grant Information** first.")
        return

    session = create_session()
    try:
        # --- Current submission status -------------------------------------
        status = get_long_format_value(session, tf_id, fy_id, "report_status", "")
        submitted_at = get_long_format_value(session, tf_id, fy_id, "report_submitted_at", "")
        if status == "submitted":
            st.info(f"✅ This report was submitted on **{submitted_at}**. "
                    "You can still edit any section and submit again to update it.")
        else:
            st.info("📝 Status: **Draft** — not yet submitted.")

        # --- Completeness check (based on saved data) ----------------------
        st.markdown("#### Completeness check")
        st.caption("Checks what you've **saved**. Save each section first, then review here.")

        results = validate_report(session, tf_id, fy_id)
        for section, missing in results.items():
            if missing:
                st.markdown(f"- ⚠️ **{section}** — missing: {', '.join(missing)}")
            else:
                st.markdown(f"- ✅ **{section}**")

        st.divider()

        # --- Submit --------------------------------------------------------
        if report_is_complete(results):
            if st.button("Submit report", type="primary", key="submit_report"):
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                update_long_format_field(session, tf_id, fy_id, "report_status", "submitted")
                update_long_format_field(session, tf_id, fy_id, "report_submitted_at", now)
                # Refresh the master Excel export in Azure Blob (background thread).
                export_report_safe()
                st.success(f"Report submitted successfully on {now}.")
                st.balloons()
                st.rerun()
        else:
            st.warning("Fill in and **Save** the items flagged above before you can submit.")
            st.button("Submit report", type="primary", key="submit_report", disabled=True)
    finally:
        session.close()
