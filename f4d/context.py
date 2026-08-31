# Auto-split from the original monolithic main.py. See git history.
import streamlit as st
from connection import create_session
from model import (
    GrantInfo, TrustFund, User,
)


def normalize(value):
    return value if value is not None else ""


# Two projects were each issued two trust-fund numbers (a clerical oddity). The
# second ("alias") login maps to the first ("primary") so both logins resolve to
# the same trust fund and share one submission. The alias login user is created
# on the primary fund's team by seed_from_master_pytds.py, so the team filter in
# the lookups still matches. Format: {alias_username: primary_username}.
_TF_ALIASES = {
    "TF0C8998_admin": "TF0C8995_admin",
    "TF0C8493_admin": "TF0C8491_admin",
}


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
            # Start every session on a blank canvas: leave current_fiscal_year_id as
            # None so basic_grant_info's switcher defaults to its first option,
            # "➕ New fiscal year report". Any saved years remain selectable there.
            # (Previously a lone saved year was auto-loaded, so FY25 surfaced on login.)
            pass
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
    # Resolve alias logins to their primary so both share one trust fund/report.
    username = current_user.username
    return _TF_ALIASES.get(username, username)


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
    # (current_username() maps alias logins to their primary fund).
    trustfund = session.query(TrustFund).filter_by(name=current_username()).first()
    
    if trustfund is None:
        st.error("No Trust Fund associated with the current user's team.")
        return None

    trustfund_id = trustfund.id
    return trustfund_id



# Keys that survive a session reset. Everything else in st.session_state is
# per-grant form state and must not carry over from one login to the next.
_SESSION_RESET_KEEP = frozenset({"logged_in", "user_id"})


def reset_session_state(keep=_SESSION_RESET_KEEP):
    """Wipe all per-report state from st.session_state.

    TTLs who report for several grants log out of one and into the next in the
    same browser tab. Streamlit keeps session_state alive for the lifetime of
    that tab, so without this every widget key, cached form value and
    ``*_loaded_for`` guard from the previous grant is still present when the
    next grant's form renders — the widget key wins over the ``value=`` the
    section passes, so the previous grant's answers appear pre-filled (and can
    be saved onto the new grant). Reloading the page was the only cure because
    a fresh page load starts a fresh Streamlit session.

    Called on both login and logout so neither direction can leak.
    """
    for key in list(st.session_state.keys()):
        if key in keep:
            continue
        try:
            del st.session_state[key]
        except Exception:
            # A key tied to a widget rendered earlier in this same run can
            # refuse deletion; the rerun that follows discards it anyway.
            pass
