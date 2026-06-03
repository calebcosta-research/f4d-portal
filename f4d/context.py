# Auto-split from the original monolithic main.py. See git history.
import streamlit as st
from connection import create_session
from model import (
    GrantInfo, TrustFund, User,
)


def normalize(value):
    return value if value is not None else ""


def _resolve_grant_context():
    """Ensure current_trustfund_id and current_fiscal_year_id are set in session state.

    Called once before rendering any 'Report new results' section so that every
    section can rely on these values being populated without each one having to
    implement its own fallback logic.
    """
    tf_id = st.session_state.get("current_trustfund_id")
    fy_id = st.session_state.get("current_fiscal_year_id")

    # Nothing to do if both are already resolved
    if tf_id and fy_id:
        return

    session = create_session()
    try:
        if not tf_id:
            trustfund = session.query(TrustFund).filter(
                TrustFund.name == current_username(),
                TrustFund.team_id == current_team_id()
            ).first()
            if trustfund:
                st.session_state.current_trustfund_id = trustfund.id
                tf_id = trustfund.id

        if tf_id and not fy_id:
            # Don't auto-select a FY if the user is deliberately creating a new report
            if st.session_state.get("bgi_creating_new"):
                return
            # Find the distinct fiscal years saved for this trustfund
            saved_fy_rows = (
                session.query(GrantInfo.fiscal_year_id)
                .filter_by(trustfund_id=tf_id, deleted=False)
                .distinct()
                .all()
            )
            saved_fy_ids = [row[0] for row in saved_fy_rows if row[0] is not None]
            if len(saved_fy_ids) == 1:
                # Only one year exists — auto-select it
                st.session_state.current_fiscal_year_id = saved_fy_ids[0]
            # If multiple years exist, leave fy_id as None; basic_grant_info's
            # switcher is the canonical place to choose between them.
    finally:
        session.close()


def current_team_id():
    session = create_session()
    current_user = session.query(User).filter_by(
        id=st.session_state.user_id).first()
    if current_user is None:
        st.error("User not found.")
        return
    team_id = current_user.team_id
    return team_id


def current_username():
    session = create_session()
    current_user = session.query(User).filter_by(
        id=st.session_state.user_id).first()
    if current_user is None:
        st.error("User not found.")
        return
    username = current_user.username
    return username


def current_grantname():
    session = create_session()
    current_grant = session.query(TrustFund).filter_by(
        name=current_username()).first()
    if current_grant is None:
        st.error("Grant not found.")
        return
    grantname = current_grant.grant
    return grantname


def current_trustfund_id():
    session = create_session()  # Create a new session
    current_user = session.query(User).filter_by(id=st.session_state.user_id).first()
    
    if current_user is None:
        st.error("User not found.")
        return None

    # Assuming there's a relationship between User and TrustFund
    trustfund = session.query(TrustFund).filter_by(name=current_user.username).first()
    
    if trustfund is None:
        st.error("No Trust Fund associated with the current user's team.")
        return None

    trustfund_id = trustfund.id
    return trustfund_id

