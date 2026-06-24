# Auto-split from the original monolithic main.py. See git history.
import ast
import datetime
import streamlit as st
from connection import create_session
from model import (
    GrantInfo,
)
from f4d.context import (
    current_team_id,
)

# Per-collaboration type dropdown options.
COLLAB_OPTIONS = [
    "Other World Bank teams (e.g. GPs)",
    "IFC",
    "IMF",
    "Other IFIs/MDBs/bilateral organizations",
    "Other organizations (e.g. CSOs, private sector, academia, think tanks)",
]

_ENTRY_FIELDS = ("type", "partner_detail", "describe", "lessons_learned")
_YES_NO = ["Yes", "No"]


def _empty_entry():
    return {k: "" for k in _ENTRY_FIELDS}


def collaboration_partnership():
    st.success("### 4. Collaboration/Partnership")

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

    session = create_session()
    tf_id = st.session_state.current_trustfund_id
    fy_id = st.session_state.current_fiscal_year_id

    existing_grant_info = session.query(GrantInfo).filter_by(
        trustfund_id=tf_id, fiscal_year_id=fy_id).first()

    # Reload widgets/entries from the DB whenever the fiscal year changes.
    if st.session_state.get("collab_loaded_for_fy") != fy_id:
        st.session_state.pop("collaborations_input", None)
        st.session_state.pop("collaboration_list", None)
        st.session_state["collab_loaded_for_fy"] = fy_id

    # ---- Top-level Yes/No question -------------------------------------------
    q_row = session.query(GrantInfo).filter_by(
        trustfund_id=tf_id, fiscal_year_id=fy_id, field="collaborations", deleted=False).first()
    saved_answer = (q_row.value or "").strip() if q_row else ""

    answer = st.radio(
        "Is the grant delivered in collaboration/partnership with other World Bank "
        "teams (e.g. other GPs), IFC, IMF, or other MDBs/IFIs/bilateral organizations? *",
        _YES_NO,
        index=_YES_NO.index(saved_answer) if saved_answer in _YES_NO else None,
        key="collaborations_input",
    )

    if st.button("Save response", key="save_collab_question", type="primary"):
        if not existing_grant_info:
            st.warning("No Grant Info exists! Please create one in Basic Grant Information subpage")
        elif answer not in _YES_NO:
            st.error("Please answer the collaboration/partnership question before saving.")
        else:
            session.query(GrantInfo).filter_by(
                trustfund_id=tf_id, fiscal_year_id=fy_id, field="collaborations").delete()
            session.add(GrantInfo(
                trustfund_id=tf_id, fiscal_year_id=fy_id, field="collaborations",
                value=answer, team_id=current_team_id(), deleted=False,
                created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()))
            session.commit()
            st.session_state.collaboration_unsaved_changes = False
            st.success("Collaboration response saved!")

    # ---- Collaboration details: only shown (and required) when answer is Yes -
    if answer != "Yes":
        if answer == "No":
            st.info("No collaboration/partnership reported for this grant.")
        session.close()
        return

    st.divider()
    st.markdown("#### Collaboration details *")
    st.caption("Because you answered **Yes**, add at least one collaboration/partnership "
               "below — each with its own type and details.")

    if "collaboration_list" not in st.session_state:
        entries = []
        for r in session.query(GrantInfo).filter_by(
                trustfund_id=tf_id, fiscal_year_id=fy_id, deleted=False).all():
            if r.field.startswith("collaboration_"):  # collaboration_1, _2, ... (not "collaborations")
                try:
                    entries.append(ast.literal_eval(r.value))
                except (ValueError, SyntaxError):
                    pass
        st.session_state["collaboration_list"] = entries
        st.session_state.setdefault("collaboration_unsaved_changes", False)

    def mark_changed():
        st.session_state.collaboration_unsaved_changes = True

    collab_to_delete = None
    for i in range(len(st.session_state["collaboration_list"])):
        entry = st.session_state["collaboration_list"][i]
        st.subheader(f"Collaboration {i + 1}")

        _type = entry.get("type", "")
        entry["type"] = st.selectbox(
            "Type of collaboration/partner",
            COLLAB_OPTIONS,
            index=COLLAB_OPTIONS.index(_type) if _type in COLLAB_OPTIONS else None,
            key=f"collab_type_{i}", on_change=mark_changed)

        entry["partner_detail"] = st.text_input(
            "Which team(s) / organization(s)?",
            value=entry.get("partner_detail", ""),
            key=f"collab_partner_{i}", on_change=mark_changed)

        entry["describe"] = st.text_area(
            "Describe the collaboration",
            placeholder="In which areas of the grant is the collaboration taking place? "
                        "What value did the partners add? What role did the World Bank play?",
            value=entry.get("describe", ""),
            key=f"collab_describe_{i}", on_change=mark_changed)

        entry["lessons_learned"] = st.text_area(
            "Lessons learned",
            placeholder="Any lessons learned from the collaboration. "
                        "How is the partnership expected to evolve?",
            value=entry.get("lessons_learned", ""),
            key=f"collab_lessons_{i}", on_change=mark_changed)

        c1, c2 = st.columns([2, 2])
        with c1:
            if st.button(f"Save Collaboration {i + 1}", key=f"save_collab_{i}"):
                session.query(GrantInfo).filter_by(
                    trustfund_id=tf_id, fiscal_year_id=fy_id,
                    field=f"collaboration_{i + 1}").delete()
                session.add(GrantInfo(
                    trustfund_id=tf_id, fiscal_year_id=fy_id, field=f"collaboration_{i + 1}",
                    value=str({k: entry.get(k, "") for k in _ENTRY_FIELDS}),
                    team_id=current_team_id(), deleted=False,
                    created_at=datetime.datetime.now(), updated_at=datetime.datetime.now()))
                session.commit()
                st.session_state.collaboration_unsaved_changes = False
                st.success(f"Collaboration {i + 1} saved successfully!")
        with c2:
            if st.button(f"Delete Collaboration {i + 1}", key=f"delete_collab_{i}"):
                collab_to_delete = i
                st.session_state.collaboration_unsaved_changes = True

    if not st.session_state["collaboration_list"]:
        st.warning("At least one collaboration is required because you answered **Yes**.")

    if st.button("Add Collaboration", key="add_collaboration", type="primary"):
        st.session_state["collaboration_list"].append(_empty_entry())
        st.session_state.collaboration_unsaved_changes = True
        st.rerun()

    # Handle deletion outside the loop to avoid index-shift issues.
    if collab_to_delete is not None:
        st.session_state["collaboration_list"].pop(collab_to_delete)
        session.query(GrantInfo).filter_by(
            trustfund_id=tf_id, fiscal_year_id=fy_id,
            field=f"collaboration_{collab_to_delete + 1}").delete()
        session.commit()
        st.session_state.collaboration_unsaved_changes = False
        st.success(f"Collaboration {collab_to_delete + 1} deleted successfully!")
        st.rerun()

    if st.session_state.get("collaboration_unsaved_changes", False):
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    session.close()
