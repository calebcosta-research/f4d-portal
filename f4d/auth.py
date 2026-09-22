# Auto-split from the original monolithic main.py. See git history.
import streamlit as st
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from connection import create_session
from model import (
    User,
)
from f4d.config import (
    super_admin_username, super_admin_password,
)
from f4d.context import reset_session_state
from f4d import telemetry
from f4d.passwords import hash_password, spend_equal_time, verify_password


def store_password_hash(session, user, password):
    """Replace a legacy plain-text (or weaker) stored password with a hash.

    Runs only after a successful check. If it fails the login still goes
    ahead; the upgrade is simply retried next time.
    """
    try:
        user.password = hash_password(password)
        session.commit()
        telemetry.event("password_upgraded", user_id=user.id)
    except Exception:  # noqa: BLE001 - never block a valid login over this
        session.rollback()
        telemetry.log.exception("password upgrade failed")


def display_login_form():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        authenticate_user(username, password)


def authenticate_user(username, password):
    with create_session() as session:
        if check_credentials(session, username, password):
            # Get user details only for non-admin login
            if username != super_admin_username:
                user = session.query(User).filter_by(username=username).first()
            else:
                user = None

            # Drop anything left over from a previous login in this browser
            # tab before installing the new user's context, so a TTL who
            # reports for several grants never sees the previous grant's
            # answers pre-filled in the next one.
            reset_session_state(keep=frozenset())

            # Update session state on successful login
            st.session_state.logged_in = True
            st.session_state.user_id = user.id if user else None
            telemetry.event("login_succeeded", user_id=user.id if user else "super_admin")
            st.success("Logged in successfully!")
            st.session_state.current_trustfund_id = None
            st.session_state.current_fiscal_year_id = None
            st.rerun()
        else:
            telemetry.event("login_failed")
            st.error("Invalid username or password.")


def check_credentials(session: Session, username: str, password: str) -> bool:
    try:
        # Check if the user table is empty
        user_count = session.query(User).count()

        # If the user table is empty, allow login with "super_admin_username and super_admin_password"
        if user_count == 0:
            return username == super_admin_username and password == super_admin_password

        # Query the user by username
        user = session.query(User).filter_by(username=username).one()
        ok, needs_rehash = verify_password(user.password, password)
        if needs_rehash:
            store_password_hash(session, user, password)
        return ok

    except NoResultFound:
        spend_equal_time(password)
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


# Function to normalize values

