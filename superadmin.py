import csv
import datetime
import os
import pandas as pd
from sqlalchemy import text
import streamlit as st
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import ast

from connection import create_session
from model import Country, F4DAssociationEnum, FiscalYear, GrantInfo, Indicator, Region, TrustFund, Team, User, TrustFundIndicatorMapping, delete_team
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Access the variables
f4d_admin_username = os.getenv("f4d_admin_username")
f4d_admin_password = os.getenv("f4d_admin_password")
super_admin_username = os.getenv("super_admin_username")
super_admin_password = os.getenv("super_admin_password")

# Set the title of the app
st.set_page_config(page_title="F4D Results Reporting for Admins",
                   layout="centered")  # wide


def main():
    # Initialize session state for user login status
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        display_main_app()
    else:
        display_login_form()


def display_login_form():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        authenticate_user(username, password)


def authenticate_user(username, password):
    with create_session() as session:
        if check_credentials(session, username, password):
            user = session.query(User).filter_by(username=username).first()
            # Update session state on successful login
            st.session_state.logged_in = True
            st.session_state.user_id = user.id if user else None
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password.")


def check_credentials(session: Session, username: str, password: str) -> bool:
    try:
        # If the user table is empty, allow login with "super_admin_username and super_admin_password"
        if username == super_admin_username and password == super_admin_password:  # user_count == 0
            return True

        # Query the user by username
        user = session.query(User).filter_by(username=username).one()
        return user.password == password

    except NoResultFound:
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def display_main_app():
    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id
    except Exception as e:
        st.error(f"An error occurred while retrieving users: {e}")

    if current_user.username == super_admin_username and current_user.password ==super_admin_password:
        page = st.sidebar.radio("Action:", [
            "Teams", "Users", "Fiscal Years", "Countries", "Regions"
        ])
    else:
        page = st.sidebar.radio("Action:", [
            "Dashboards", "Grants", "Pillars", "Tiers", "Indicators", "Map Grants to Indicators"
        ])

    col1, col2 = st.columns([6, 1])  # Adjust the width of the columns

    with col1:
        pass

    with col2:
        if st.button("Logout", type="primary"):
            st.session_state.logged_in = False
            current_user = None
            st.session_state.user_id = None
            st.success("Logged out successfully!")
            st.rerun()

    # Call the corresponding function based on the selected page
    if page == "Teams":
        manage_teams()
    elif page == "Users":
        manage_users()
    elif page == "Fiscal Years":
        manage_fiscalyear()
    elif page == "Indicators":
        manage_indicators()
    elif page == "Grants":
        manage_trustfunds(team_id)
    elif page == "Pillars":
        manage_pillars()
    elif page == "Tiers":
        manage_tiers()
    elif page == "Countries":
        manage_countries()
    elif page == "Regions":
        manage_regions()
    elif page == "Map Grants to Indicators":
        manage_mappings()
    elif page == "Dashboards":
        dashboards(team_id)


def manage_teams():
    st.title("Manage Teams")

    # Create a session
    session = create_session()

    try:
        # Add new trust fund
        with st.form("add_team"):
            team = st.text_input("Team Name")
            submitted = st.form_submit_button("Add Team")
            if submitted:
                new_team = Team(
                    team=team, created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                session.add(new_team)
                try:
                    session.commit()
                    st.success(f"Added team: {team}")
                    st.rerun()

                except IntegrityError:
                    session.rollback()
                    st.error("Failed to add team. It may already exist.")

        # Search box for filtering trust funds
        search_query = st.text_input(
            "Search Teams", "", key=f"team_name_search")

        # Display existing trust funds
        teams = session.query(Team).filter(Team.deleted == False).all()
        if teams:
            # Filter trust funds based on the search query
            filtered_teams = [
                tf for tf in teams if search_query.lower() in tf.team.lower()]
            for team in filtered_teams:
                with st.expander(f"Team: {team.team}"):
                    new_name = st.text_input(
                        "Team", value=team.team, key=f"team_name_{team.id}")

                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        if st.button("Update", key=f"update_{team.id}"):
                            team.team = new_name
                            team.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(f"Updated team to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{team.id}"):
                            with create_session() as session:
                                if delete_team(session, team.id):
                                    st.success(f"Deleted team: {team.team}")
                                    st.rerun()
                                else:
                                    st.error(
                                        f"Cannot delete team: {team.team}; it has associated users.")

        else:
            st.write("No teams found.")

    except Exception as e:
        st.error(f"An error occurred while managing teams: {e}")

    finally:
        session.close()


def manage_users():
    st.title("Manage Users")

    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id
    except Exception as e:
        st.error(f"An error occurred while retrieving users: {e}")

    # Upload CSV file
    uploaded_file = st.file_uploader(
        f"Upload CSV file with Users", type="csv")
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        if 'username' in df.columns and 'password' in df.columns and 'team' in df.columns:
            # Check if the table is empty
            users = session.query(User).filter(
                User.team_id == team_id, User.username.like('TF%')).all()

            if not users:
                # If empty, insert all entries from the CSV
                for index, row in df.iterrows():
                    # Look up the team_id based on the team name provided in the row
                    team_name = row['team'] if pd.notna(row['team']) else None

                    team_id = None
                    if team_name:
                        team = session.query(Team).filter(
                            Team.team == team_name).first()
                        if team:
                            team_id = team.id
                    new_user = User(
                        username=row['username'] if pd.notna(
                            row['username']) else None,
                        password=row['password'] if pd.notna(
                            row['password']) else None,

                        # How to put the id of the team here
                        team_id=team_id,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_user)
                session.commit()
                st.success(f"Users added from CSV file.")
            else:
                # Ask if the user wants to overwrite existing data
                overwrite = st.radio(
                    "The table is not empty. Do you want to overwrite existing data?",
                    options=["No", "Yes"]
                )
                if overwrite == "Yes":
                    # Overwrite existing data
                    session.query(User).filter(
                        User.team_id == team_id, User.username.like('TF%')).delete(synchronize_session=False)
                    for index, row in df.iterrows():
                        try:
                            # Look up the team_id based on the team name provided in the row
                            team_name = row['team'] if pd.notna(
                                row['team']) else None

                            team_id = None
                            if team_name:
                                team = session.query(Team).filter(
                                    Team.team == team_name).first()
                                if team:
                                    team_id = team.id

                            new_user = User(
                                username=row['username'] if pd.notna(
                                    row['username']) else None,
                                password=row['password'] if pd.notna(
                                    row['password']) else None,
                                team_id=team_id,
                                created_at=datetime.datetime.now(),
                                updated_at=datetime.datetime.now()
                            )
                            session.add(new_user)

                        except KeyError as ke:
                            print(f"KeyError for row index {index}: {ke}")
                        except Exception as e:
                            print(
                                f"Error adding user for row index {index}: {e}")
                    session.commit()
                    st.success(
                        f"Existing users overwritten with data from CSV file.")
                else:
                    st.warning(
                        f"Upload canceled. Existing users remain unchanged.")
        else:
            st.error(
                "CSV file must contain 'username', 'password' and 'team' columns.")

    try:
        # Add new user
        with st.form("add_user"):
            username = st.text_input("Email (Username)")
            password = st.text_input("Password", type="password")
            # Fetch all teams from the database
            teams = session.query(Team).filter(Team.deleted == False).all()

            # Create a list of tuples (team name, team id)
            team_options = [(team.team, team.id) for team in teams]

            # Use st.selectbox to display team names and save the corresponding team id
            selected_team_name, team_id = st.selectbox(
                "Select Team", team_options, format_func=lambda x: x[0]
            )

            submitted = st.form_submit_button("Add User")
            if submitted:
                new_user = User(
                    username=username,
                    password=password,
                    team_id=team_id,
                    created_at=datetime.datetime.now(),
                    updated_at=datetime.datetime.now()
                )
                session.add(new_user)
                try:
                    session.commit()
                    st.success(f"Added user: {username}")
                    st.rerun()

                except IntegrityError:
                    session.rollback()
                    st.error("Failed to add user. Username may already exist.")

        # Search box for filtering users
        search_query = st.text_input(
            "Search Users", "", key="user_name_search")

        # Display existing users
        users = session.query(User).filter(User.deleted == False).all()
        if users:
            # Filter users based on the search query
            filtered_users = [
                u for u in users if search_query.lower() in u.username.lower()]
            for user in filtered_users:
                with st.expander(f"User: {user.username}"):
                    new_username = st.text_input(
                        "Email (Username)", value=user.username, key=f"user_name_{user.id}")

                    # Fetch all teams from the database
                    teams = session.query(Team).filter(
                        Team.deleted == False).all()

                    # Create a list of team IDs and names
                    team_ids = [team.id for team in teams]
                    team_names = [team.team for team in teams]

                    # Determine the default index for the selectbox
                    if user.team_id in team_ids:
                        default_index = team_ids.index(user.team_id)
                    else:
                        default_index = 0

                    # Use st.selectbox to display team names and save the corresponding team id
                    new_team_id = st.selectbox(
                        "Select Team", team_ids, index=default_index, key=f"team_id_{user.id}", format_func=lambda x: team_names[team_ids.index(x)]
                    )
                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        if st.button("Update", key=f"update_{user.id}"):
                            user.username = new_username
                            user.team_id = new_team_id
                            user.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(f"Updated user to: {new_username}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{user.id}"):
                            user.deleted = True
                            user.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(f"Deleted user: {user.username}")
                            st.rerun()

        else:
            st.write("No users found.")

    except Exception as e:
        st.error(f"An error occurred while managing users: {e}")

    finally:
        session.close()


def manage_fiscalyear():
    st.title("Manage Fiscal Years")

    # Create a session
    session = create_session()

    try:
        # Add new trust fund
        with st.form("add_fy"):
            fy = st.text_input("Fiscal Year")
            submitted = st.form_submit_button("Add Fiscal Year")
            if submitted:
                new_fy = FiscalYear(
                    fy=fy, created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                session.add(new_fy)
                try:
                    session.commit()
                    st.success(f"Added fiscal year: {fy}")
                    st.rerun()

                except IntegrityError:
                    session.rollback()
                    st.error("Failed to add fiscal year. It may already exist.")

        # Search box for filtering trust funds
        search_query = st.text_input(
            "Search Fiscal Years", "", key=f"fy_search")

        # Display existing fiscal years
        fys = session.query(FiscalYear).filter(
            FiscalYear.deleted == False).all()
        if fys:
            # Filter fiscal years based on the search query
            filtered_fys = [
                fy for fy in fys if search_query.lower() in fy.fy.lower()]
            for fy in filtered_fys:
                with st.expander(f"Fiscal Year: {fy.fy}"):
                    new_name = st.text_input(
                        "Fiscal Year", value=fy.fy, key=f"fiscalyear_{fy.id}")

                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        if st.button("Update", key=f"update_{fy.id}"):
                            fy.fy = new_name
                            fy.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(f"Updated fiscal year to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{fy.id}"):
                            fy.deleted = True
                            fy.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted team: {fy.fy}")
                            st.rerun()

        else:
            st.write("No fiscal years found.")

    except Exception as e:
        st.error(f"An error occurred while managing fiscal years: {e}")

    finally:
        session.close()


def manage_trustfunds(team_id):
    st.info("#### Add New Grant")
    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id

        # Upload CSV file
        st.warning("###### Upload Grants")  
        uploaded_file = st.file_uploader(
            f"Bulk upload CSV file with Grants", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if 'trustfund_id' in df.columns and 'pcode' in df.columns and 'grant' in df.columns and 'ttl' in df.columns:
                # Check if the table is empty
                trustfunds = session.query(TrustFund).filter_by(
                    project_type="Trust Fund").all()

                if not trustfunds:
                    # If empty, insert all entries from the CSV
                    for index, row in df.iterrows():
                        pcode = row['pcode'] if 'pcode' in row and pd.notna(
                            row['pcode']) else None
                        grant = row['grant'] if 'grant' in row and pd.notna(
                            row['grant']) else None
                        ttl = row['ttl'] if 'ttl' in row and pd.notna(
                            row['ttl']) else None

                        new_trustfund = TrustFund(
                            project_type="Trust Fund",
                            name=row['trustfund_id'],
                            description=None,
                            pcode=pcode,
                            grant=grant,
                            ttl=ttl,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_trustfund)
                    session.commit()
                    st.success(f"Grants added from CSV file.")
                else:
                    # Ask if the user wants to overwrite existing data
                    overwrite = st.radio(
                        "The table is not empty. Do you want to overwrite existing data?",
                        options=["No", "Yes"]
                    )
                    if overwrite == "Yes":
                        # Overwrite existing data
                        session.query(TrustFund).filter(
                            TrustFund.project_type == "Trust Fund", TrustFund.team_id == team_id).delete()
                        for index, row in df.iterrows():
                            try:
                                pcode = row['pcode'] if 'pcode' in row and pd.notna(
                                    row['pcode']) else None
                                grant = row['grant'] if 'grant' in row and pd.notna(
                                    row['grant']) else None
                                ttl = row['ttl'] if 'ttl' in row and pd.notna(
                                    row['ttl']) else None

                                if 'id' in row and pd.notna(row['id']):
                                    name_value = str(row['id'])
                                    # Convert numeric value to integer string if it is numeric
                                    name = str(int(float(name_value))) if name_value.replace(
                                        '.', '', 1).isdigit() else name_value
                                else:
                                    name = ''
                                new_trustfund = TrustFund(
                                    project_type="Trust Fund",
                                    name=row['trustfund_id'],
                                    description=None,
                                    pcode=pcode,
                                    grant=grant,
                                    ttl=ttl,
                                    team_id=team_id,
                                    created_at=datetime.datetime.now(),
                                    updated_at=datetime.datetime.now()
                                )
                                session.add(new_trustfund)

                            except KeyError as ke:
                                print(f"KeyError for row index {index}: {ke}")
                            except Exception as e:
                                print(
                                    f"Error adding Grant for row index {index}: {e}")
                        session.commit()
                        st.success(
                            f"Existing Grants overwritten with data from CSV file.")
                    else:
                        st.warning(
                            f"Upload canceled. Existing Grants remain unchanged.")
            else:
                st.error(
                    "CSV file must contain 'trustfund_id', 'pcode', 'grant' and 'ttl' columns.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.warning("###### Add Grant")
        # Add new project
        with st.expander("Add Grant"):
            with st.form("add_project"):
                entry_name = st.text_input(f"Grant ID")
                entry_grant = st.text_input("Grant Name")
                entry_ttl = st.text_input("TTL Name")
                entry_pcode = st.text_input("Pcode")
                
                
                submitted = st.form_submit_button("Add", type="primary")
                if submitted:
                    if entry_name:
                        new_trustfund = TrustFund(
                            project_type="Trust Fund",
                            name=entry_name,
                            description=None,
                            pcode=entry_pcode,
                            grant=entry_grant,
                            ttl=entry_ttl,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_trustfund)
                        try:
                            session.commit()
                            st.success(f"Added Grant: {entry_name}")
                            st.rerun()
                        except IntegrityError:
                            session.rollback()
                            st.error(
                                f"Failed to add Grant. It may already exist.")
                    else:
                        st.warning("Please provide Trust Fund ID (#).")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.info("#### Modify/Delete existing Grants")
        # Search box for filtering projects
        search_query = st.text_input(
            f"Search Grants", "", key=f"trustfund_search")

        # Display existing entries
        trustfunds = session.query(TrustFund).filter(TrustFund.project_type == "Trust Fund",
                                                     TrustFund.team_id == team_id, TrustFund.deleted == False).all()
        if search_query:
            # Filter trustfunds based on the search query
            filtered_trustfunds = [
                proj for proj in trustfunds if search_query.lower() in proj.name.lower() or search_query.lower() in proj.pcode.lower() or search_query.lower() in proj.grant.lower()]
            for trustfund in filtered_trustfunds:
                trustfund_display = f"{trustfund.name} - {trustfund.pcode} - {trustfund.grant}" if trustfund.grant and trustfund.pcode else trustfund.name
                with st.expander(f"{trustfund_display}"):
                    new_name = st.text_input(
                        f"Grant ID", value=trustfund.name, key=f"trustfund_id_{trustfund.id}")
                    new_grant = st.text_input(
                        f"Grant Name", value=trustfund.grant, key=f"grant_{trustfund.id}")
                    new_ttl = st.text_input(
                        f"TTL Name", value=trustfund.ttl, key=f"ttl_{trustfund.id}")
                    new_pcode = st.text_input(
                        f"Pcode", value=trustfund.pcode, key=f"pcode_{trustfund.id}")
                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        if st.button("Update", key=f"update_{trustfund.id}"):
                            trustfund.name = new_name
                            trustfund.description = None
                            trustfund.pcode = new_pcode
                            trustfund.grant = new_grant
                            trustfund.ttl = new_ttl
                            trustfund.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Updated Grant to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{trustfund.id}"):
                            trustfund.deleted = True
                            trustfund.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted Grant: {trustfund.name}")
                            st.rerun()

        else:
            st.write(f"No Grants found.")



    except Exception as e:
        st.error(f"An error occurred while managing Grants: {e}")

    finally:
        session.close()


def manage_pillars():
    st.info("#### Add New Pillar")

    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id


        # Upload CSV file
        st.warning("###### Upload Pillars")
        uploaded_file = st.file_uploader(
            f"Bulk upload CSV file with Pillars", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if 'name' in df.columns:
                # Check if the table is empty
                trustfunds = session.query(TrustFund).filter_by(
                    project_type="Pillar").all()

                if not trustfunds:
                    # If empty, insert all entries from the CSV
                    for index, row in df.iterrows():
                        if 'name' in row and pd.notna(row['name']):
                            name_value = str(row['name'])
                            # Convert numeric value to integer string if it is numeric
                            name = str(int(float(name_value))) if name_value.replace(
                                '.', '', 1).isdigit() else name_value
                        else:
                            name = ''
                        new_trustfund = TrustFund(
                            project_type="Pillar",
                            name=name,
                            description=row['description'] if pd.notna(
                                row['description']) else '',
                            pcode=None,
                            grant=None,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_trustfund)
                    session.commit()
                    st.success(f"Pillars added from CSV file.")
                else:
                    # Ask if the user wants to overwrite existing data
                    overwrite = st.radio(
                        "The table is not empty. Do you want to overwrite existing data?",
                        options=["No", "Yes"]
                    )
                    if overwrite == "Yes":
                        # Overwrite existing data
                        session.query(TrustFund).filter(
                            TrustFund.project_type == "Pillar", TrustFund.team_id == team_id).delete()
                        for index, row in df.iterrows():
                            try:
                                if 'name' in row and pd.notna(row['name']):
                                    name_value = str(row['name'])
                                    # Convert numeric value to integer string if it is numeric
                                    name = str(int(float(name_value))) if name_value.replace(
                                        '.', '', 1).isdigit() else name_value
                                else:
                                    name = ''
                                new_trustfund = TrustFund(
                                    project_type="Pillar",
                                    name=name,
                                    description=row['description'] if pd.notna(
                                        row['description']) else '',
                                    pcode=None,
                                    grant=None,
                                    team_id=team_id,
                                    created_at=datetime.datetime.now(),
                                    updated_at=datetime.datetime.now()
                                )
                                session.add(new_trustfund)

                            except KeyError as ke:
                                print(f"KeyError for row index {index}: {ke}")
                            except Exception as e:
                                print(
                                    f"Error adding Pillar for row index {index}: {e}")
                        session.commit()
                        st.success(
                            f"Existing Pillars overwritten with data from CSV file.")
                    else:
                        st.warning(
                            f"Upload canceled. Existing Pillars remain unchanged.")
            else:
                st.error(
                    "CSV file must contain 'name' and 'description' columns.")
        
        st.markdown("</br></br>", unsafe_allow_html=True)
        st.warning("###### Add Pillar")
        # Add new project
        with st.expander("Add Pillar"):
            with st.form("add_project"):
                entry_name = st.text_input(f"Pillar")
                entry_description = st.text_input(f"Description")
                submitted = st.form_submit_button("Add", type="primary")
                if submitted:
                    if entry_name:
                        new_trustfund = TrustFund(
                            project_type="Pillar",
                            name=entry_name,
                            description=entry_description,
                            pcode=None,
                            grant=None,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_trustfund)
                        try:
                            session.commit()
                            st.success(f"Added Pillar: {entry_name}")
                            st.rerun()
                        except IntegrityError:
                            session.rollback()
                            st.error(
                                f"Failed to add Pillar. It may already exist.")
                    else:
                        st.warning("Please provide Pillar.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.info("#### Modify/Delete existing Pillars")
        # Search box for filtering projects
        search_query = st.text_input(
            f"Search Pillars", "", key=f"pillar_search")

        # Display existing entries
        trustfunds = session.query(TrustFund).filter(TrustFund.project_type == "Pillar",
                                                     TrustFund.team_id == team_id, TrustFund.deleted == False).all()
        if search_query:
            # Filter trustfunds based on the search query
            filtered_trustfunds = [
                proj for proj in trustfunds if search_query.lower() in proj.name.lower()]
            for trustfund in filtered_trustfunds:
                trustfund_display = f"{trustfund.name} - {trustfund.description}" if trustfund.description else trustfund.name
                with st.expander(f"Pillar: {trustfund_display}"):
                    new_name = st.text_input(
                        f"Pillar", value=trustfund.name, key=f"pillar_name_{trustfund.id}")
                    new_description = st.text_input(
                        f"Description", value=trustfund.description, key=f"pillar_description_{trustfund.id}")
                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        if st.button("Update", key=f"update_{trustfund.id}"):
                            trustfund.name = new_name
                            trustfund.description = new_description
                            trustfund.pcode = None
                            trustfund.grant = None
                            trustfund.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Updated Pillar to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{trustfund.id}"):
                            trustfund.deleted = True
                            trustfund.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted Pillar: {trustfund.name}")
                            st.rerun()

        else:
            st.write(f"No Pillars found.")

    except Exception as e:
        st.error(f"An error occurred while managing Pillars: {e}")

    finally:
        session.close()


def manage_tiers():
    st.info("#### Add Tier")

    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id

        # Upload CSV file
        st.warning("###### Upload Tiers")
        uploaded_file = st.file_uploader(
            f"Bulk upload CSV file with Tiers", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if 'name' in df.columns and 'description' in df.columns:
                # Check if the table is empty
                trustfunds = session.query(TrustFund).filter_by(
                    project_type="Tier").all()

                if not trustfunds:
                    # If empty, insert all entries from the CSV
                    for index, row in df.iterrows():
                        if 'name' in row and pd.notna(row['name']):
                            name_value = str(row['name'])
                            # Convert numeric value to integer string if it is numeric
                            name = str(int(float(name_value))) if name_value.replace(
                                '.', '', 1).isdigit() else name_value
                        new_trustfund = TrustFund(
                            project_type="Tier",
                            name=name,
                            description=row['description'] if pd.notna(
                                row['description']) else '',
                            pcode=None,
                            grant=None,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_trustfund)
                    session.commit()
                    st.success(f"Tiers added from CSV file.")
                else:
                    # Ask if the user wants to overwrite existing data
                    overwrite = st.radio(
                        "The table is not empty. Do you want to overwrite existing data?",
                        options=["No", "Yes"]
                    )
                    if overwrite == "Yes":
                        # Overwrite existing data
                        session.query(TrustFund).filter(
                            TrustFund.project_type == "Tier", TrustFund.team_id == team_id).delete()
                        for index, row in df.iterrows():
                            try:
                                # Handle the row['name'] conversion
                                if 'name' in row and pd.notna(row['name']):
                                    name_value = str(row['name'])
                                    # Convert numeric value to integer string if it is numeric
                                    name = str(int(float(name_value))) if name_value.replace(
                                        '.', '', 1).isdigit() else name_value
                                else:
                                    name = ''
                                new_trustfund = TrustFund(
                                    project_type="Tier",
                                    name=name,
                                    description=row['description'] if pd.notna(
                                        row['description']) else '',
                                    pcode=None,
                                    grant=None,
                                    team_id=team_id,
                                    created_at=datetime.datetime.now(),
                                    updated_at=datetime.datetime.now()
                                )
                                session.add(new_trustfund)

                            except KeyError as ke:
                                print(f"KeyError for row index {index}: {ke}")
                            except Exception as e:
                                print(
                                    f"Error adding Tier for row index {index}: {e}")
                        session.commit()
                        st.success(
                            f"Existing TTiers overwritten with data from CSV file.")
                    else:
                        st.warning(
                            f"Upload canceled. Existing Tiers remain unchanged.")
            else:
                st.error(
                    "CSV file must contain 'name' and 'description' columns.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.warning("###### Add Tier")
        # Add new tier
        with st.expander("Add Tier"):
            with st.form("add_project"):
                entry_name = st.text_input("Tier")
                entry_description = st.text_input("Description")

                submitted = st.form_submit_button("Add", type="primary")

                # Check if the form is submitted
                if submitted:
                    if entry_name:
                        new_trustfund = TrustFund(
                            project_type="Tier",
                            name=entry_name,
                            description=entry_description,
                            pcode=None,
                            grant=None,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_trustfund)
                        try:
                            session.commit()
                            st.success(f"Added Tier: {entry_name}")
                            st.rerun()
                        except IntegrityError:
                            session.rollback()
                            st.error(
                                "Failed to add Tier. It may already exist.")
                    else:
                        st.warning("Please provide Tier.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.info("#### Modify/Delete existing Tiers")
        # Search box for filtering projects
        search_query = st.text_input(
            f"Search Tiers", "", key=f"tier_search")

        # Display existing entries
        trustfunds = session.query(TrustFund).filter(TrustFund.project_type == "Tier",
                                                     TrustFund.team_id == team_id, TrustFund.deleted == False).all()
        if search_query:
            # Filter trustfunds based on the search query
            filtered_trustfunds = [
                proj for proj in trustfunds if search_query.lower() in proj.name.lower()]
            for trustfund in filtered_trustfunds:
                trustfund_display = f"{trustfund.name} - {trustfund.description}" if trustfund.description else trustfund.name
                with st.expander(f"Tier: {trustfund_display}"):
                    new_name = st.text_input(
                        f"Tier", value=trustfund.name, key=f"tier_name_{trustfund.id}")
                    new_description = st.text_input(
                        f"Description", value=trustfund.description, key=f"tier_description_{trustfund.id}")
                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        if st.button("Update", key=f"update_{trustfund.id}"):
                            trustfund.name = new_name
                            trustfund.description = new_description
                            trustfund.pcode = None
                            trustfund.grant = None
                            trustfund.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Updated Tier to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{trustfund.id}"):
                            trustfund.deleted = True
                            trustfund.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted Tier: {trustfund.name}")
                            st.rerun()

        else:
            st.write(f"No Tiers found.")

    except Exception as e:
        st.error(f"An error occurred while managing Tiers: {e}")

    finally:
        session.close()


def manage_countries():
    st.title("Manage Countries")

    # Create a session
    session = create_session()

    try:
        # Upload CSV file
        uploaded_file = st.file_uploader(
            "Upload CSV file with Countries", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if 'Country' in df.columns:
                # Check if the table is empty
                countries = session.query(Country).all()
                if not countries:
                    # If empty, insert all codes from the CSV
                    for index, row in df.iterrows():
                        new_country = Country(
                            country=row['Country'], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                        session.add(new_country)
                    session.commit()
                    st.success("Countries added from CSV file.")
                    # st.rerun()
                else:
                    # Ask if the user wants to overwrite existing data
                    overwrite = st.radio(
                        "The table is not empty. Do you want to overwrite existing data?",
                        options=["No", "Yes"]
                    )
                    if overwrite == "Yes":
                        # Overwrite existing data
                        session.query(Country).delete()
                        for index, row in df.iterrows():
                            new_country = Country(
                                country=row['Country'], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                            session.add(new_country)
                        session.commit()
                        st.success(
                            f"Existing countries overwritten with data from CSV file.")
                    else:
                        st.warning(
                            f"Upload canceled. Existing countries remain unchanged.")
            else:
                st.error("CSV file must contain a column named 'Country'.")

        # Add new country
        with st.form("add_country"):
            country = st.text_input("Country")
            submitted = st.form_submit_button("Add Country")
            if submitted:
                new_country = Country(
                    country=country, created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                session.add(new_country)
                try:
                    session.commit()
                    st.success(f"Added country: {country}")
                    st.rerun()

                except IntegrityError:
                    session.rollback()
                    st.error("Failed to add country. It may already exist.")

        # Search box for filtering project codes
        search_query = st.text_input(
            "Search Country", "", key=f"country_search")

        # Display existing project codes
        countries = session.query(Country).filter(
            Country.deleted == False).all()
        if countries:
            # Filter countries based on the search query
            filtered_countries = [
                cou for cou in countries if search_query.lower() in cou.country.lower()]
            for country in filtered_countries:
                with st.expander(f"Country: {country.country}"):
                    new_name = st.text_input(
                        "Country", value=country.country, key=f"country_{country.id}")

                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        if st.button("Update", key=f"update_{country.id}"):
                            country.country = new_name
                            country.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(f"Updated country to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{country.id}"):
                            country.deleted = True
                            country.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted country: {country.country}")
                            st.rerun()

        else:
            st.write("No countries found.")

    except Exception as e:
        st.error(f"An error occurred while managing countries: {e}")

    finally:
        session.close()


def manage_regions():
    st.title("Manage Regions")

    # Create a session
    session = create_session()

    try:
        # Upload CSV file
        uploaded_file = st.file_uploader(
            "Upload CSV file with Regions", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if 'Region' in df.columns:
                # Check if the table is empty
                regions = session.query(Region).all()
                if not regions:
                    # If empty, insert all codes from the CSV
                    for index, row in df.iterrows():
                        new_region = Region(
                            region=row['Region'], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                        session.add(new_region)
                    session.commit()
                    st.success("Regions added from CSV file.")
                    # st.rerun()
                else:
                    # Ask if the user wants to overwrite existing data
                    overwrite = st.radio(
                        "The table is not empty. Do you want to overwrite existing data?",
                        options=["No", "Yes"]
                    )
                    if overwrite == "Yes":
                        # Overwrite existing data
                        session.query(Region).delete()
                        for index, row in df.iterrows():
                            new_region = Region(
                                region=row['Region'], created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                            session.add(new_region)
                        session.commit()
                        st.success(
                            f"Existing regions overwritten with data from CSV file.")
                    else:
                        st.warning(
                            f"Upload canceled. Existing regions remain unchanged.")
            else:
                st.error("CSV file must contain a column named 'Region'.")

        # Add new project title
        with st.form("add_region"):
            region = st.text_input("Region")
            submitted = st.form_submit_button("Add Regions")
            if submitted:
                new_region = Region(
                    region=region, created_at=datetime.datetime.now(), updated_at=datetime.datetime.now())
                session.add(new_region)
                try:
                    session.commit()
                    st.success(f"Added region: {region}")
                    st.rerun()

                except IntegrityError:
                    session.rollback()
                    st.error("Failed to add region. It may already exist.")

        # Search box for filtering project codes
        search_query = st.text_input(
            "Search Region", "", key=f"region_search")

        # Display existing project codes
        regions = session.query(Region).filter(Region.deleted == False).all()
        if regions:
            # Filter regions based on the search query
            filtered_regions = [
                reg for reg in regions if search_query.lower() in reg.region.lower()]
            for region in filtered_regions:
                with st.expander(f"Region: {region.region}"):
                    new_name = st.text_input(
                        "Region", value=region.region, key=f"region_{region.id}")

                    # Create 5 columns for buttons
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        if st.button("Update", key=f"update_{region.id}"):
                            region.region = new_name
                            region.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(f"Updated region to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{region.id}"):
                            region.deleted = True
                            region.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted region: {region.region}")
                            st.rerun()

        else:
            st.write("No regions found.")

    except Exception as e:
        st.error(f"An error occurred while managing regions: {e}")

    finally:
        session.close()


def manage_indicators():
    st.info("#### Add New Indicator/Deliverable")

    # Create a session
    session = create_session()

    # Initialize session state for subindicator count if not already done
    if 'subindicator_count' not in st.session_state:
        st.session_state.subindicator_count = 0

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id

        current_team = session.query(Team).filter_by(
            id=team_id).first()
        if current_team is None:
            st.error("Team not found.")
            return
        team = current_team.team

        

        # Upload CSV file
        st.warning("###### Upload Indicators/Deliverables") 
        uploaded_file = st.file_uploader(
            "Bulk upload CSV file with Indicators/Deliverables", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            # Check for necessary columns
            required_columns = [
                'indicator_id', 'indicator_name', 'standard_indicator_name', 'parent_id', 'indicator_prompt',
                'pillar_info', 'tier_info', 'indicator_definition', 'unit_of_measurement', 'categorical_unit', 'custom_indicator', 'indicator_conversion'
            ]
            if all(col in df.columns for col in required_columns):
                # Check if the table is empty
                indicators = session.query(Indicator).filter(
                    Indicator.deleted == False, Indicator.team_id == team_id).all()
                if not indicators:
                    # If empty, insert all indicators from the CSV
                    for index, row in df.iterrows():
                        new_indicator = Indicator(
                            indicator_id=f"{team}_{row['indicator_id']}",
                            parent_id=f"{team}_{row['parent_id']}" if pd.notna(
                                row['parent_id']) else None,
                            indicator_name=row['indicator_name'] if pd.notna(
                                row['indicator_name']) else None,
                            standard_indicator_name=row['standard_indicator_name'] if pd.notna(
                                row['standard_indicator_name']) else None,
                            indicator_prompt=row['indicator_prompt'] if pd.notna(
                                row['indicator_prompt']) else None,
                            pillar_info=row['pillar_info'] if pd.notna(
                                row['pillar_info']) else None,
                            tier_info=int(row['tier_info']) if pd.notna(
                                row['tier_info']) else None,
                            indicator_definition=row['indicator_definition'] if pd.notna(
                                row['indicator_definition']) else None,
                            unit_of_measurement=row['unit_of_measurement'] if pd.notna(
                                row['unit_of_measurement']) else None,
                            categorical_unit=row['categorical_unit'] if pd.notna(
                                row['categorical_unit']) else None,
                            custom_indicator=row['custom_indicator'] if pd.notna(
                                row['custom_indicator']) else None,
                            indicator_conversion=row['indicator_conversion'] if pd.notna(
                                row['indicator_conversion']) else None,
                            team_id=team_id,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_indicator)
                    session.commit()
                    st.success("Indicators/Deliverables added from CSV file.")
                else:
                    # Ask if the user wants to overwrite existing data
                    overwrite = st.radio(
                        "The table is not empty. Do you want to overwrite existing data?",
                        options=["No", "Yes"]
                    )
                    if overwrite == "Yes":
                        # Overwrite existing data
                        session.query(Indicator).delete()
                        for index, row in df.iterrows():
                            new_indicator = Indicator(
                                indicator_id=f"{team}_{row['indicator_id']}",
                                parent_id=f"{team}_{row['parent_id']}" if pd.notna(
                                    row['parent_id']) else None,
                                indicator_name=row['indicator_name'] if pd.notna(
                                    row['indicator_name']) else None,
                                standard_indicator_name=row['standard_indicator_name'] if pd.notna(
                                    row['standard_indicator_name']) else None,
                                indicator_prompt=row['indicator_prompt'] if pd.notna(
                                    row['indicator_prompt']) else None,
                                pillar_info=row['pillar_info'] if pd.notna(
                                    row['pillar_info']) else None,
                                tier_info=int(row['tier_info']) if pd.notna(
                                    row['tier_info']) else None,
                                indicator_definition=row['indicator_definition'] if pd.notna(
                                    row['indicator_definition']) else None,
                                unit_of_measurement=row['unit_of_measurement'] if pd.notna(
                                    row['unit_of_measurement']) else None,
                                categorical_unit=row['categorical_unit'] if pd.notna(
                                    row['categorical_unit']) else None,
                                custom_indicator=row['custom_indicator'] if pd.notna(
                                    row['custom_indicator']) else None,
                                indicator_conversion=row['indicator_conversion'] if pd.notna(
                                    row['indicator_conversion']) else None,
                                team_id=team_id,
                                created_at=datetime.datetime.now(),
                                updated_at=datetime.datetime.now()
                            )
                            session.add(new_indicator)
                        session.commit()
                        st.success(
                            "Existing indicators/deliverables overwritten with data from CSV file.")
                    else:
                        st.warning(
                            "Upload canceled. Existing indicators/deliverables remain unchanged.")
            else:
                st.error("CSV file must contain all required columns.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.warning("###### Add Indicator/Deliverable")
        # Add new indicator
        with st.expander("Indicator/Deliverable"):
            col1, col2 = st.columns([1, 14])  # Adjust the ratio as needed

            # Display the team identifier in the first column
            with col1:
                st.markdown(
                    f"<div style='font-weight:bold; background-color:#f0f0f0; border:1px solid #F0F2F6; border-radius: 10px; padding:6px 5px; margin-top:28px; margin-right:-15px'>{team.upper()}_</div>", unsafe_allow_html=True)

            # Display the text input in the second column
            with col2:
                indicator_id_part = st.text_input(
                    label="*Indicator ID", placeholder="P1_T1_1")
            indicator_id = f"{team.upper()}_{indicator_id_part}"
            indicator_name = st.text_input("*Indicator/Deliverable Name")
            indicator_prompt = st.text_area("Indicator/Deliverable Prompt", "")

            unit_of_measurement = st.selectbox("Unit of Measurement", [
                "", "Date", "Number", "Short Text", "Long Text", "Percentage", "Categorical"])
            categorical_unit = None
            if "Categorical" in unit_of_measurement:
                categorical_unit = st.text_input(
                    "Categorical units", help="Separate each unit by ',' such as Yes, No")

            # Fetching Pillars
            pillars = session.query(TrustFund).filter(
                TrustFund.project_type == "Pillar", TrustFund.deleted == False, TrustFund.team_id == team_id).all()
            pillar_options = [pillar.name for pillar in pillars] if pillars else [
                "No Pillars available"]

            # Fetching Tiers
            tiers = session.query(TrustFund).filter(
                TrustFund.project_type == "Tier", TrustFund.deleted == False, TrustFund.team_id == team_id).all()
            tier_options = [tier.name for tier in tiers] if tiers else [
                "No Tiers available"]

            # Dropdown for selecting Pillar and Tier
            selected_pillar = st.selectbox("Select Pillar", pillar_options)
            selected_tier = st.selectbox("Select Tier", tier_options)

            indicator_definition = st.text_area(
                "Indicator/Deliverable Definition", "")
            custom_indicator = st.checkbox("Custom Indicator", "")
            standard_indicator_name = st.text_input("Standard Indicator Name")
            indicator_conversion = st.text_input(
                "Custom to Standard Conversion")

        # Expander for subindicators
        with st.expander("Subindicators/Subdeliverables"):
            subindicator_count = st.number_input(
                "Number of Subindicators/Subdeliverables", min_value=0, max_value=10, value=0, step=1)

            # Update session state when the number of subindicators changes
            if subindicator_count != st.session_state.subindicator_count:
                st.session_state.subindicator_count = subindicator_count

            subindicators = []
            for i in range(st.session_state.subindicator_count):
                col1, col2 = st.columns([1, 5])
                # Display the team identifier in the first column
                with col1:
                    st.markdown(
                        f"<div style='font-weight:bold; background-color:#f0f0f0; border:1px solid #F0F2F6; border-radius: 10px; padding:6px 5px; margin-top:28px; margin-right:-15px'>{team.upper()}_{indicator_id_part}</div>", unsafe_allow_html=True)

                # Display the text input in the second column
                with col2:
                    subindicator_id_part = st.text_input(
                        label=f"*{i + 1} - Subindicator ID", key=f"subindicator_id_{i}", placeholder="a")
                subindicator_id = f"{team.upper()}_{indicator_id_part}{subindicator_id_part}"
                subindicator_name = st.text_input(
                    f"*{i + 1} - Subindicator/Subdeliverable Name", key=f"subindicator_name_{i}")
                subindicator_prompt = st.text_area(
                    f"{i + 1} - Subindicator/Subdeliverable Prompt", key=f"subindicator_prompt_{i}")
                
                subindicator_unit_of_measurement = st.selectbox(
                    f"{i + 1} - Select Subindicator/Subdeliverable Unit of Measurement",
                    ["", "Date", "Number", "Short Text",
                        "Long Text", "Percentage", "Categorical"],
                    key=f"subindicator_unit_of_measurement_{i}"
                )

                # Initialize subindicator_categorical_unit
                subindicator_categorical_unit = None

                if "Categorical" in subindicator_unit_of_measurement:
                    subindicator_categorical_unit = st.text_input(
                        f"{i + 1} - Subindicator/Subdeliverable Categorical units",  key=f"subindicator_units_{i}", help="Separate each unit by ',' such as Yes, No")
                    
                subindicator_definition = st.text_area(
                    f"{i + 1} - Subindicator/Subdeliverable Definition", key=f"subindicator_definition_{i}")


                subindicator_custom_indicator = st.checkbox(
                    f"{i + 1} - Subindicator Custom Indicator", key=f"subindicator_custom_indicator_{i}")
                
                subindicator_standard_name = st.text_input(
                    f"{i + 1} - Subindicator Standard Name", key=f"subindicator_standard_name_{i}")
                
                subindicator_indicator_conversion = st.text_input(
                    f"{i + 1} - Subindicator/Subdeliverable Custom to Standard Conversion", key=f"subindicator_indicator_conversion_{i}")
                # Append only if the ID is provided
                if subindicator_id:
                    subindicators.append({
                        "id": subindicator_id,
                        "name": subindicator_name,
                        "standard_name": subindicator_standard_name,
                        "prompt": subindicator_prompt,
                        "pillar_info": selected_pillar,
                        "tier_info": selected_tier,
                        "definition": subindicator_definition,
                        "unit_of_measurement": subindicator_unit_of_measurement,
                        "categorical_unit": subindicator_categorical_unit,
                        "custom_indicator": subindicator_custom_indicator,
                        "indicator_covnersion": subindicator_indicator_conversion,
                    })

        # Button for adding the indicator and subindicators
        if st.button("Add Indicator/Deliverable", type="primary"):
            # Check if id and name are not empty
            if indicator_id and indicator_name:
                new_indicator = Indicator(
                    indicator_id=indicator_id,
                    indicator_name=indicator_name,
                    standard_indicator_name=standard_indicator_name or None,
                    indicator_prompt=indicator_prompt or None,
                    pillar_info=selected_pillar or None,
                    tier_info=selected_tier or None,
                    indicator_definition=indicator_definition or None,
                    unit_of_measurement=unit_of_measurement or None,
                    categorical_unit=categorical_unit,
                    custom_indicator=custom_indicator or None,
                    indicator_conversion=indicator_conversion or None,
                    team_id=team_id,
                    created_at=datetime.datetime.now(),
                    updated_at=datetime.datetime.now()
                )
                session.add(new_indicator)

                # Add subindicators to the session
                for sub in subindicators:
                    new_subindicator = Indicator(
                        indicator_id=sub['id'],
                        indicator_name=sub['name'],
                        standard_indicator_name=sub['standard_name'],
                        indicator_prompt=sub['prompt'],
                        pillar_info=selected_pillar,
                        tier_info=selected_tier,
                        indicator_definition=sub['definition'],
                        unit_of_measurement=sub['unit_of_measurement'],
                        categorical_unit=sub['categorical_unit'],
                        custom_indicator=sub['custom_indicator'],
                        indicator_conversion=sub['indicator_conversion'],
                        parent_id=new_indicator.indicator_id,
                        team_id=team_id,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_subindicator)

                try:
                    session.commit()
                    st.success(
                        f"Added indicator/deliverable: {indicator_id} with {len(subindicators)} subindicators.")
                    st.session_state.subindicator_count = 0
                    st.rerun()
                except IntegrityError:
                    session.rollback()
                    st.error(
                        "Failed to add indicator/deliverable. It may already exist.")
            else:
                st.warning("Please provide both Indicator ID and Name.")

        st.markdown("</br></br>", unsafe_allow_html=True)   
        st.info("### Modify/Delete existing Indicators/Deliverables")
        # Search box for filtering indicators
        search_query = st.text_input(
            "Search Indicator/Deliverable", "", key="indicator_search")

        # Display existing indicators
        indicators = session.query(Indicator).filter(
            Indicator.deleted == False, Indicator.parent_id == None, Indicator.team_id == team_id).all()
        if search_query:
            # Filter indicators based on the search query
            filtered_indicators = [
                ind for ind in indicators if search_query.lower() in ind.indicator_name.lower() or
                search_query.lower() in ind.indicator_id.lower()
            ]

            for indicator in filtered_indicators:
                with st.expander(f"{indicator.indicator_id} - {indicator.indicator_name}"):
                    # Create two columns for layout
                    col1, col2 = st.columns([1, 14])

                    # Display the team identifier in the first column
                    with col1:
                        st.markdown(
                            f"<div style='font-weight:bold; background-color:#f0f0f0; border:1px solid #F0F2F6; border-radius: 10px; padding:6px 5px; margin-top:28px; margin-right:-15px'>{team.upper()}_</div>",
                            unsafe_allow_html=True
                        )

                    # Display the text input in the second column
                    with col2:
                        new_id_part = st.text_input(
                            label="Indicator ID",
                            value=indicator.indicator_id.split("_", 1)[1],
                            key=f"indicatorid_{indicator.id}"
                        )
                    new_id = f"{team.upper()}_{new_id_part}"
                    new_name = st.text_input(
                        "Indicator/Deliverable Name", value=indicator.indicator_name, key=f"indicatorname_{indicator.id}")
                    new_standard_name = st.text_input(
                        "Standard Indicator Name", value=indicator.standard_indicator_name, key=f"standardindicatorname_{indicator.id}")
                    new_prompt = st.text_area(
                        "Indicator/Deliverable Prompt", value=indicator.indicator_prompt, key=f"prompt_{indicator.id}")

                    new_selected_pillar = st.selectbox(
                        "Select Pillar",
                        pillar_options,
                        index=pillar_options.index(
                            indicator.pillar_info) if indicator.pillar_info in pillar_options else 0,
                        key=f"pillar_{indicator.id}"
                    )

                    new_selected_tier = st.selectbox(
                        "Select Tier",
                        tier_options,
                        index=tier_options.index(
                            indicator.tier_info) if indicator.tier_info in tier_options else 0,
                        key=f"tier_{indicator.id}"
                    )
                    new_definition = st.text_area(
                        "Indicator/Deliverable Definition", value=indicator.indicator_definition, key=f"definition_{indicator.id}")
                    new_unit = st.selectbox(
                        "Unit of Measurement",
                        ["", "Date", "Number", "Short Text",
                         "Long Text", "Percentage", "Categorical"],
                        index=["", "Date", "Number", "Short Text",
                               "Long Text", "Percentage", "Categorical"].index(indicator.unit_of_measurement) if indicator.unit_of_measurement in [
                            "", "Date", "Number", "Short Text",
                            "Long Text", "Percentage", "Categorical"] else 0,
                        key=f"unit_{indicator.id}"
                    )
                    if "Categorical" in new_unit:
                        new_category_unit = st.text_input(
                            "Categorical Unit", value=indicator.categorical_unit, key=f"indicator_categoricalunit_{indicator.id}")
                    else:
                        new_category_unit = None

                    new_custom_indicator = st.checkbox(
                        "Custom Indicator", value=indicator.custom_indicator, key=f"custom_indicator_{indicator.id}")

                    new_indicator_conversion = st.text_input(
                        "Custom to Standard Conversion", value=indicator.indicator_conversion, key=f"indicatorconversion_{indicator.id}")
                    # Create 5 columns for buttons
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Update", key=f"update_{indicator.id}"):
                            indicator.indicator_id = new_id
                            indicator.indicator_name = new_name
                            indicator.standard_indicator_name = new_standard_name
                            indicator.indicator_prompt = new_prompt
                            indicator.pillar_info = new_selected_pillar
                            indicator.tier_info = new_selected_tier
                            indicator.indicator_definition = new_definition
                            indicator.unit_of_measurement = new_unit
                            indicator.categorical_unit = new_category_unit
                            indicator.custom_indicator = new_custom_indicator
                            indicator.indicator_conversion = new_indicator_conversion
                            indicator.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Updated indicator/deliverable to: {new_name}")
                            st.rerun()

                    with col2:
                        if st.button("Delete", key=f"delete_{indicator.id}"):
                            indicator.deleted = True
                            indicator.updated_at = datetime.datetime.now()
                            session.commit()
                            st.success(
                                f"Deleted indicator/deliverable: {indicator.indicator_name}")
                            st.rerun()

                    # Display subindicators
                    subindicators = session.query(Indicator).filter(
                        Indicator.deleted == False, Indicator.parent_id == indicator.indicator_id).all()
                    if subindicators:
                        st.subheader("Subindicators/Subdeliverables")
                        for index, subindicator in enumerate(subindicators, start=1):

                            # Create two columns for layout
                            col1, col2 = st.columns([1, 5])

                            # Display the team identifier in the first column
                            with col1:
                                st.markdown(
                                    f"<div style='font-weight:bold; background-color:#f0f0f0; border:1px solid #F0F2F6; border-radius: 10px; padding:6px 5px; margin-top:28px; margin-right:-15px'>{new_id}</div>",
                                    unsafe_allow_html=True
                                )

                            # Display the text input for Subindicator ID in the second column
                            with col2:
                                subindicator_id_part = st.text_input(
                                    label=f"{index} - Subindicator ID",
                                    value=subindicator.indicator_id.replace(
                                        new_id, ""),
                                    key=f"subindicator_id_{subindicator.id}",
                                    placeholder="Enter subindicator ID"
                                )

                            sub_new_id = f"{new_id}{subindicator_id_part}"
                            sub_new_name = st.text_input(
                                f"{index}-Subindicator/Deliverable Name", value=subindicator.indicator_name, key=f"subindicatorname_{subindicator.id}")
                            sub_new_standard_name = st.text_input(
                                f"{index}-Subindicator Standard Name", value=subindicator.standard_indicator_name, key=f"subindicatorstandardname_{subindicator.id}")
                            sub_new_prompt = st.text_area(
                                f"{index}-Subindicator/Deliverable Prompt", value=subindicator.indicator_prompt, key=f"subindicator_prompt_{subindicator.id}")

                            sub_new_definition = st.text_area(
                                f"{index}-Subindicator/Deliverable Definition", value=subindicator.indicator_definition, key=f"subindicator_definition_{subindicator.id}")

                            sub_new_unit = st.selectbox(
                                f"{index} - Unit of Measurement",
                                ["", "Date", "Number", "Short Text",
                                 "Long Text", "Percentage", "Categorical"],
                                index=["", "Date", "Number", "Short Text",
                                       "Long Text", "Percentage", "Categorical"].index(subindicator.unit_of_measurement) if subindicator.unit_of_measurement in [
                                    "",  "Date", "Number", "Short Text",
                                    "Long Text", "Percentage", "Categorical"] else 0,
                                key=f"subindicator_unit_{subindicator.id}"
                            )
                            if "Categorical" in sub_new_unit:
                                sub_new_categorical_unit = st.text_input(
                                    f"{index}-Subindicator Categorical Unit", value=subindicator.categorical_unit, key=f"subindicatorcategoricalunit_{subindicator.id}")
                            else:
                                sub_new_categorical_unit = None

                            sub_new_custom_indicator = st.checkbox(
                                f"{index}-Custom Indicator", value=subindicator.custom_indicator, key=f"subindicator_custom_indicator_{subindicator.id}")
                            sub_new_conversion_indicator = st.text_input(
                                f"{index}-Subindicator Custom to Standard Conversion", value=subindicator.indicator_conversion, key=f"subindicatorconversion_{subindicator.id}")
                            # Create columns for update and delete buttons for the subindicator
                            sub_col1, sub_col2 = st.columns(2)
                            with sub_col1:
                                if st.button("Update Subindicator/Subdeliverable", key=f"update_sub_{subindicator.id}"):
                                    subindicator.indicator_id = sub_new_id
                                    subindicator.indicator_name = sub_new_name
                                    subindicator.standard_indicator_name = sub_new_standard_name
                                    subindicator.indicator_prompt = sub_new_prompt
                                    subindicator.pillar_info = new_selected_pillar
                                    subindicator.tier_info = new_selected_tier
                                    subindicator.indicator_definition = sub_new_definition
                                    subindicator.unit_of_measurement = sub_new_unit
                                    subindicator.categorical_unit = sub_new_categorical_unit
                                    subindicator.custom_indicator = sub_new_custom_indicator
                                    subindicator.indicator_conversion = sub_new_conversion_indicator
                                    subindicator.updated_at = datetime.datetime.now()
                                    session.commit()
                                    st.success(
                                        f"Updated subindicator/subdeliverable to: {sub_new_name}")
                                    st.rerun()

                            with sub_col2:
                                if st.button("Delete Subindicator/Subdeliverable", key=f"delete_sub_{subindicator.id}"):
                                    subindicator.deleted = True
                                    subindicator.updated_at = datetime.datetime.now()
                                    session.commit()
                                    st.success(
                                        f"Deleted subindicator/subdeliverable: {subindicator.indicator_name}")
                                    st.rerun()

        else:
            st.write("No indicators/deliverables found.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.info("### Export Indicators/Deliverables")
        manage_exports(team_id=team_id)

    except Exception as e:
        st.error(
            f"An error occurred while managing indicators/deliverables: {e}")

    finally:
        session.close()


def manage_mappings():
    st.info("#### Add New Mapping")

    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id

        current_team = session.query(Team).filter_by(
            id=team_id).first()
        if current_team is None:
            st.error("Team not found.")
            return
        team = current_team.team

        # Fetch existing trust funds and indicators
        trustfunds = session.query(TrustFund).filter(
            TrustFund.project_type == "Trust Fund", TrustFund.deleted == False, TrustFund.team_id == team_id).order_by(TrustFund.name).all()
        indicators = session.query(Indicator).filter(
            Indicator.deleted == False, Indicator.team_id == team_id).all()

        # Upload CSV file
        st.warning("###### Upload Mappings")
        uploaded_file = st.file_uploader(
            f"Bulk upload CSV file with Mappings", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if 'trustfund_id' in df.columns and 'indicator_id' in df.columns and 'relationship' in df.columns:
                try:
                    mappings = session.query(TrustFundIndicatorMapping).filter(
                        TrustFundIndicatorMapping.team_id == team_id).all()
                    if not mappings:
                        # If empty, insert all entries from the CSV
                        missing_ids = []  # List to track rows with missing trustfund_id or indicator_id
                        for index, row in df.iterrows():
                            trustfund_name = row['trustfund_id'].strip()
                            ind_id = f"{team}_"+row['indicator_id'].strip()
                            relation = row.get('relationship', "").strip()
                            try:
                                trustfund_id = next(
                                    tf.id for tf in trustfunds if tf.name == trustfund_name
                                )
                            except StopIteration:
                                trustfund_id = None
                                print(
                                    f"Error processing row {index}: trustfund_id cannot be found")

                            try:
                                indicator_id = next(
                                    i.id for i in indicators if i.indicator_id == ind_id
                                )
                            except StopIteration:
                                indicator_id = None
                                print(
                                    f"Error processing row {index}: indicator_id cannot be found")

                            # Check if both IDs are present before creating a new mapping
                            if trustfund_id is not None and indicator_id is not None:
                                new_mapping = TrustFundIndicatorMapping(
                                    trustfund_id=trustfund_id,
                                    indicator_id=indicator_id,
                                    relation_ship=relation,
                                    team_id=team_id,
                                    created_at=datetime.datetime.now(),
                                    updated_at=datetime.datetime.now()
                                )
                                session.add(new_mapping)
                            else:
                                # Track the row index if trustfund_id or indicator_id is None
                                if trustfund_id is None:
                                    missing_ids.append(
                                        f"Row {index + 1} (Trust Fund)")
                                if indicator_id is None:
                                    missing_ids.append(
                                        f"Row {index + 1} (Indicator)")

                        # Check if there are any missing trustfund_id or indicator_id warnings to report
                        if missing_ids:
                            st.warning(
                                f"Could not create mappings for the following rows: {', '.join(missing_ids)}. "
                                "Please check the Trust Fund IDs and Indicator IDs."
                            )
                        else:
                            session.commit()
                            st.success(f"Mappings added from CSV file.")

                    else:
                        # Ask if the user wants to overwrite existing data
                        overwrite = st.radio(
                            "The table is not empty. Do you want to overwrite existing data?",
                            options=["No", "Yes"]
                        )
                        if overwrite == "Yes":
                            # Overwrite existing data
                            session.query(TrustFundIndicatorMapping).filter(
                                TrustFundIndicatorMapping.team_id == team_id).delete()
                            missing_ids = []  # List to track rows with missing trustfund_id or indicator_id
                            for index, row in df.iterrows():
                                trustfund_name = row['trustfund_id'].strip()
                                ind_id = f"{team}_"+row['indicator_id'].strip()
                                relation = row.get('relationship', "").strip()
                                try:
                                    trustfund_id = next(
                                        tf.id for tf in trustfunds if tf.name == trustfund_name
                                    )
                                except StopIteration:
                                    trustfund_id = None
                                    print(
                                        f"Error processing row {index}: trustfund_id cannot be found")

                                try:
                                    indicator_id = next(
                                        i.id for i in indicators if i.indicator_id == ind_id
                                    )
                                except StopIteration:
                                    indicator_id = None
                                    print(
                                        f"Error processing row {index}: indicator_id cannot be found")

                                # Check if both IDs are present before creating a new mapping
                                if trustfund_id is not None and indicator_id is not None:
                                    new_mapping = TrustFundIndicatorMapping(
                                        trustfund_id=trustfund_id,
                                        indicator_id=indicator_id,
                                        relation_ship=relation,
                                        team_id=team_id,
                                        created_at=datetime.datetime.now(),
                                        updated_at=datetime.datetime.now()
                                    )
                                    session.add(new_mapping)
                                else:
                                    # Track the row index if trustfund_id or indicator_id is None
                                    if trustfund_id is None:
                                        missing_ids.append(
                                            f"Row {index + 1} (Trust Fund)")
                                    if indicator_id is None:
                                        missing_ids.append(
                                            f"Row {index + 1} (Indicator)")

                            # Check if there are any missing trustfund_id or indicator_id warnings to report
                            if missing_ids:
                                st.warning(
                                    f"Could not create mappings for the following rows: {', '.join(missing_ids)}. "
                                    "Please check the Trust Fund IDs and Indicator IDs in the mappings.csv file."
                                )
                            else:
                                session.commit()
                                st.success(
                                    f"Existing Mappings overwritten with data from CSV file.")

                        else:
                            st.warning(
                                f"Upload canceled. Existing Mappings remain unchanged.")
                except Exception as e:
                    st.error(f"An error occurred while uploading: {e}")
            else:
                st.error(
                    "CSV file must contain 'trustfund_id', 'indicator_id' and 'relationship' columns.")

        st.markdown("</br></br>", unsafe_allow_html=True)
        st.warning("###### Add Mapping")
        selected_trustfund = st.selectbox(
            "Select Grant ID",
            options=[
                f"{tf.name}" for tf in trustfunds
            ]
        )

        indicator_options = []
        identation_char = '---'

        for indicator in indicators:
            if indicator.parent_id is None:
                # Main indicator
                option = f"{indicator.indicator_id} - {indicator.indicator_name}" if indicator.indicator_name else f"{indicator.indicator_id}"
                indicator_options.append(option)

                # Find and add subindicators
                subindicators = [
                    sub for sub in indicators if sub.parent_id == indicator.indicator_id]
                for subindicator in subindicators:
                    sub_option = f"{identation_char}{subindicator.indicator_id} - {subindicator.indicator_name}" if subindicator.indicator_name else f"{identation_char}{subindicator.indicator_id}"
                    indicator_options.append(sub_option)

        # Create the selectbox with the generated options
        selected_indicator = st.selectbox(
            "Select Indicator",
            options=indicator_options,
        )

        selected_relation = st.selectbox("Select Relationship",
                                         options=["Optional", "Mandatory"])

        # Button to map trust fund with the selected indicator
        if st.button("Map Grant to Indicator", type="primary"):

            selected_trustfund_name = selected_trustfund.split(
                ' - ')[0]  # Get the trust fund id
            # selected_pcode = selected_trustfund.split(
            #     ' - ')[1]  # Get the pcode
            # selected_grant = selected_trustfund.split(
            #     ' - ')[2]  # Get the grant
            trustfund_id = next(
                # and tf.pcode == selected_pcode and tf.grant == selected_grant
                tf.id for tf in trustfunds if tf.name == selected_trustfund_name
            )

            selected_indicator_id = selected_indicator.split(
                ' - ')[0].replace(identation_char, "").strip()  # Get the indicator ID part
            indicator_id = next(
                i.id for i in indicators if i.indicator_id == selected_indicator_id
            )

            new_mapping = TrustFundIndicatorMapping(
                trustfund_id=trustfund_id,
                indicator_id=indicator_id,
                relation_ship=selected_relation,
                team_id=team_id,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_mapping)
            session.commit()
            st.success(
                f"Mapped {selected_trustfund} with {selected_indicator}.")
            st.rerun()

        st.markdown("</br></br>", unsafe_allow_html=True)
        # Display existing mappings
        st.info("#### Modify/Delete existing Mappings") 
        search_query = st.text_input(
            "Search Mappings", placeholder="Search by Grant or Indicator", key="mapping_search")

        selected_trustfund_name = selected_trustfund.split(
            ' - ')[0]  # Get the trust fund id
        # selected_pcode = selected_trustfund.split(
        #     ' - ')[1]  # Get the pcode
        # selected_grant = selected_trustfund.split(
        #     ' - ')[2]  # Get the grant
        trustfund_id = next(
            # and tf.pcode == selected_pcode and tf.grant == selected_grant
            tf.id for tf in trustfunds if tf.name == selected_trustfund_name
        )
        # Fetch existing mappings with delete filter
        # All mappings for the team
        mappings = session.query(TrustFundIndicatorMapping).filter(
            TrustFundIndicatorMapping.deleted == False, TrustFundIndicatorMapping.team_id == team_id).all() #, TrustFundIndicatorMapping.trustfund_id == trustfund_id).all()

        # Filter mappings based on the search query
        filtered_mappings = []
        if search_query:
            for mapping in mappings:
                trustfund = session.get(TrustFund, mapping.trustfund_id)
                indicator = session.get(Indicator, mapping.indicator_id)

                if (search_query.lower() in trustfund.name.lower() or
                    # search_query.lower() in trustfund.pcode.lower() or
                    # search_query.lower() in trustfund.grant.lower() or
                    search_query.lower() in indicator.indicator_name.lower() or
                        search_query.lower() in indicator.indicator_id.lower()):
                    filtered_mappings.append((trustfund, indicator, mapping))

            # Display filtered mappings
            for trustfund, indicator, mapping in filtered_mappings:
                # trustfund_display = f"{trustfund.name} - {trustfund.pcode} - {trustfund.grant}" if trustfund.grant and trustfund.pcode else trustfund.name
                trustfund_display = f"{trustfund.name}"
                if mapping.relation_ship == "Mandatory":
                    sign = "[M]"
                else:
                    sign = "[O]"

                with st.expander(f"{sign} {trustfund_display} <-> {indicator.indicator_id} - {indicator.indicator_name}"):
                    # Option to delete the mapping
                    if st.button(f"Delete Mapping", key=f"delete_mapping_{mapping.id}"):
                        mapping.deleted = True
                        session.commit()
                        st.success(
                            f"Deleted mapping of {indicator.indicator_name} from {trustfund.name}.")
                        st.rerun()
        
        # Export buttons section
        st.markdown("</br></br>", unsafe_allow_html=True)
        st.info("#### Export Mappings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Export All Mappings", type="secondary"):
                # Export all mappings to CSV
                export_data = []
                all_mappings = session.query(TrustFundIndicatorMapping).filter(
                    TrustFundIndicatorMapping.deleted == False, 
                    TrustFundIndicatorMapping.team_id == team_id
                ).all()
                
                for mapping in all_mappings:
                    trustfund = session.get(TrustFund, mapping.trustfund_id)
                    indicator = session.get(Indicator, mapping.indicator_id)
                    export_data.append({
                        'trustfund_id': trustfund.name,
                        'indicator_id': indicator.indicator_id, #indicator.indicator_id.replace(f"{team}_", ""),
                        'relationship': mapping.relation_ship
                    })
                
                if export_data:
                    export_df = pd.DataFrame(export_data)
                    csv = export_df.to_csv(index=False)
                    st.download_button(
                        label="Download All Mappings CSV",
                        data=csv,
                        file_name=f"all_mappings_{team}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No mappings found to export.")
        
        with col2:
            if st.button("Export Selected Grant ID Mappings", type="secondary"):
                # Export mappings for selected trustfund only
                export_data = []
                selected_mappings = session.query(TrustFundIndicatorMapping).filter(
                    TrustFundIndicatorMapping.deleted == False,
                    TrustFundIndicatorMapping.team_id == team_id,
                    TrustFundIndicatorMapping.trustfund_id == trustfund_id
                ).all()
                
                for mapping in selected_mappings:
                    trustfund = session.get(TrustFund, mapping.trustfund_id)
                    indicator = session.get(Indicator, mapping.indicator_id)
                    export_data.append({
                        'trustfund_id': trustfund.name,
                        'indicator_id': indicator.indicator_id, #indicator.indicator_id.replace(f"{team}_", ""),
                        'relationship': mapping.relation_ship
                    })
                
                if export_data:
                    export_df = pd.DataFrame(export_data)
                    csv = export_df.to_csv(index=False)
                    st.download_button(
                        label=f"Download {selected_trustfund_name} Mappings CSV",
                        data=csv,
                        file_name=f"mappings_{selected_trustfund_name}_{team}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning(f"No mappings found for {selected_trustfund_name}.")

    except Exception as e:
        st.error(f"An error occurred while mapping: {e}")

    finally:
        session.close()


def manage_exports(team_id):
    session = create_session()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Export Indicators", type="primary", key="export_grants_indicators"):
            export_grants_indicator(
                session, f"Indicator_{timestamp}.csv", team_id=team_id)

        if st.button("Export Deliverables", type="primary", key="export_grants_deliverables"):
            export_grants_deliverable(
                session, f"Deliverable_{timestamp}.csv", team_id=team_id)
    with col2:
        if st.button("Export All Indicators", type="primary"):
            export_all_grants_indicator(
                session, f"All_Indicators_{timestamp}.csv", team_id=team_id)

        if st.button("Export All Deliverables", type="primary", key="export_all_deliverables"):
            export_all_grants_deliverable(
                session, f"All_Deliverables_{timestamp}.csv", team_id=team_id)


def export_grants_deliverable(session, filename, team_id):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "ttl", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "deliverable_name", "standard_indicator_name", "indicator_conversion", "deliverable_input_value", "deliverable_progress", "deliverable_description", "deliverable_data_source", "deliverable_next_steps", "deliverable_supporting_materials_url"
    ]

    # Fetch all records from the GrantInfo table
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, GrantInfo.deleted == False).all()

    # Group records by trustfund_id and fiscal_year_id to reconstruct wide format
    grouped_grants = {}
    for grant_info in grant_infos:
        key = (grant_info.trustfund_id, grant_info.fiscal_year_id)
        if key not in grouped_grants:
            grouped_grants[key] = {}
        grouped_grants[key][grant_info.field] = grant_info


    # Prepare data for CSV
    csv_data = []

    for (trustfund_id, fiscal_year_id), grant_fields in grouped_grants.items():
        try:
            # Reconstruct the grant info from long format fields
            reconstructed_grant = type('GrantInfo', (), {
                'trustfund_id': trustfund_id,
                'fiscal_year_id': fiscal_year_id
            })()

            # Extract field values from long format
            country = grant_fields.get('country').value if 'country' in grant_fields else ''
            region_id = grant_fields.get('region_id').value if 'region_id' in grant_fields else None
            p_code_instrument = grant_fields.get('p_code_instrument').value if 'p_code_instrument' in grant_fields else ''
            p_code_description = grant_fields.get('p_code_description').value if 'p_code_description' in grant_fields else ''
            f4d_association = grant_fields.get('f4d_association').value if 'f4d_association' in grant_fields else None
            pillars = grant_fields.get('pillars').value if 'pillars' in grant_fields else ''
            ccts = grant_fields.get('ccts').value if 'ccts' in grant_fields else ''
            
            # Parse JSON fields
            pillar_explanations_str = grant_fields.get('pillar_explanations').value if 'pillar_explanations' in grant_fields else '{}'
            cct_explanations_str = grant_fields.get('cct_explanations').value if 'cct_explanations' in grant_fields else '{}'
            operations_str = grant_fields.get('operations').value if 'operations' in grant_fields else '{}'
            cpfs_str = grant_fields.get('cpfs').value if 'cpfs' in grant_fields else '{}'
            deliverables_str = grant_fields.get('deliverables').value if 'deliverables' in grant_fields else '{}'
            
            # Parse other fields
            challenges = grant_fields.get('challenges').value if 'challenges' in grant_fields else ''
            strategic_objective = grant_fields.get('strategic_objective').value if 'strategic_objective' in grant_fields else ''
            overall_progress = grant_fields.get('overall_progress').value if 'overall_progress' in grant_fields else ''
            implementation_challenges = grant_fields.get('implementation_challenges').value if 'implementation_challenges' in grant_fields else ''
            public_communication_external = grant_fields.get('public_communication_external').value if 'public_communication_external' in grant_fields else ''
            public_communication_internal = grant_fields.get('public_communication_internal').value if 'public_communication_internal' in grant_fields else ''
            collaborations = grant_fields.get('collaborations').value if 'collaborations' in grant_fields else ''
            other_teams = grant_fields.get('other_teams').value if 'other_teams' in grant_fields else ''
            other_ifis = grant_fields.get('other_ifis').value if 'other_ifis' in grant_fields else ''
            other_orgs = grant_fields.get('other_orgs').value if 'other_orgs' in grant_fields else ''
            describe_collaboration = grant_fields.get('describe_collaboration').value if 'describe_collaboration' in grant_fields else ''
            lessons_learned = grant_fields.get('lessons_learned').value if 'lessons_learned' in grant_fields else ''
            
            # Check each field for None before evaluating
            pillar_explanations_dict = ast.literal_eval(pillar_explanations_str) if pillar_explanations_str and pillar_explanations_str != '{}' else {}
            cct_explanations_dict = ast.literal_eval(cct_explanations_str) if cct_explanations_str and cct_explanations_str != '{}' else {}
            operations_dict = ast.literal_eval(operations_str) if operations_str and operations_str != '{}' else {}
            cpfs_dict = ast.literal_eval(cpfs_str) if cpfs_str and cpfs_str != '{}' else {}
            deliverables_dict = ast.literal_eval(deliverables_str) if deliverables_str and deliverables_str != '{}' else {}

            region_name = ''
            if region_id:
                region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                if region:
                    region_name = region.region

            trustfund_name = ''
            ttl_name = ''
            if reconstructed_grant.trustfund_id:
                tf = session.query(TrustFund).filter_by(id=reconstructed_grant.trustfund_id, deleted=False).first()
                if tf:
                    trustfund_name = tf.name
                    ttl_name = tf.ttl if tf.ttl else ''

            fiscal_year = ''
            if reconstructed_grant.fiscal_year_id:
                fy = session.query(FiscalYear).filter_by(id=reconstructed_grant.fiscal_year_id, deleted=False).first()
                if fy:
                    fiscal_year = fy.fy

            # Create a base row without deliverables
            base_row = {
                "trustfund": trustfund_name,
                "ttl": ttl_name,
                "fiscal_year": fiscal_year,
                "country": country,
                "p_code_instrument": p_code_instrument,
                "p_code_description": p_code_description,
                "f4d_association": (
                    F4DAssociationEnum(f4d_association).value
                    if f4d_association is not None else None
                ),
                "region": region_name if region_name else '',
                "pillars": pillars if pillars else '',
                "ccts": ccts if ccts else '',
                "pillar_1_explanation": pillar_explanations_dict.get("Pillar 1: Strengthening Financial Sector Resiliency", ""),
                "pillar_2_explanation": pillar_explanations_dict.get("Pillar 2: Financing the Poor and Vulnerable", ""),
                "pillar_3_explanation": pillar_explanations_dict.get("Pillar 3: Financing the Real Economy", ""),
                "pillar_4_explanation": pillar_explanations_dict.get("Pillar 4: Developing Financial Markets", ""),
                "cct_explanation_1": cct_explanations_dict.get("Climate change and sustainable finance", ""),
                "cct_explanation_2": cct_explanations_dict.get("Advancing digitalization", ""),
                "cct_explanation_3": cct_explanations_dict.get("Financing solutions to close gender gaps", ""),
                "challenges": challenges,
                "strategic_objective": strategic_objective,
                "overall_progress": overall_progress,
                "implementation_challenges": implementation_challenges,
                "public_communication_external": public_communication_external,
                "public_communication_internal": public_communication_internal,
                "collaborations": collaborations,
                "other_teams": other_teams,
                "other_ifis": other_ifis,
                "other_orgs": other_orgs,
                "describe_collaboration": describe_collaboration,
                "lessons_learned": lessons_learned

            }
            # Handle operations dynamically
            if operations_dict:
                for key, value in operations_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            base_row[f"operation_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"operation_{nested_key}_{key}" not in headers:
                                headers.append(f"operation_{nested_key}_{key}")

            # Handle CPFS dynamically
            if cpfs_dict:
                for key, value in cpfs_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            base_row[f"cpf_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"cpf_{nested_key}_{key}" not in headers:
                                headers.append(f"cpf_{nested_key}_{key}")

            indicators = session.query(Indicator).filter(
                Indicator.team_id == team_id, Indicator.deleted == False).all()

            indicator_name_map = {
                indicator.id: {
                    "standard_name": indicator.standard_indicator_name,
                    "custom_name": indicator.indicator_name,
                    "indicator_conversion": indicator.indicator_conversion
                } for indicator in indicators
            }

            # Handle deliverables dynamically
            if deliverables_dict:
                for key, value in deliverables_dict.items():
                    if key and isinstance(value, dict):
                        # Get standard and custom names from the mapping
                        indicator_info = indicator_name_map.get(
                            int(key), {"standard_name": "", "custom_name": "", "indicator_conversion": ""})

                        standard_indicator_name = indicator_info["standard_name"]
                        deliverable_name = indicator_info["custom_name"]
                        indicator_conversion = indicator_info["indicator_conversion"]

                        # Access the nested value directly from `value`
                        deliverable_info = value

                        # Ensure deliverable_info is a dictionary
                        if isinstance(deliverable_info, dict):
                            # Create a new row for each deliverable
                            deliverable_row = base_row.copy()  # Copy the base row
                            deliverable_row["deliverable_name"] = deliverable_name
                            deliverable_row["standard_indicator_name"] = standard_indicator_name
                            deliverable_row["indicator_conversion"] = indicator_conversion
                            deliverable_row["deliverable_input_value"] = deliverable_info.get(
                                "input_value", "")
                            deliverable_row["deliverable_progress"] = deliverable_info.get(
                                "progress", "")
                            deliverable_row["deliverable_description"] = deliverable_info.get(
                                "description", "")
                            deliverable_row["deliverable_data_source"] = deliverable_info.get(
                                "data_source", "")
                            deliverable_row["deliverable_next_steps"] = deliverable_info.get(
                                "next_steps", "")
                            deliverable_row["deliverable_supporting_materials_url"] = deliverable_info.get(
                                "supporting_materials_url", "")

                            # Append the deliverable row to csv_data
                            csv_data.append(deliverable_row)

        except Exception as e:
            print(f"Error processing grant info id {grant_info.id}: {e}")

    # Write data to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for data in csv_data:
            writer.writerow(data)
        st.success("Data have been exported!")

    # Read the CSV file to provide for download
    with open(filename, "rb") as f:
        csv_file = f.read()

    # Use st.download_button to allow file download
    st.download_button(
        label="Download CSV",
        data=csv_file,
        file_name=filename,
        mime='text/csv'
    )

    # Delete the file after download
    os.remove(filename)


def export_grants_indicator(session, filename, team_id):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "ttl", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "indicator_name", "standard_indicator_name", "indicator_conversion", "indicator_input_value", "indicator_baseline_value", "indicator_year_baseline", "indicator_progress", "indicator_target_value", "indicator_year_target", "indicator_data_collection", "indicator_level_of_result"
    ]

    # Fetch all records from the GrantInfo table
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, GrantInfo.deleted == False).all()

    # Group records by trustfund_id and fiscal_year_id to reconstruct wide format
    grouped_grants = {}
    for grant_info in grant_infos:
        key = (grant_info.trustfund_id, grant_info.fiscal_year_id)
        if key not in grouped_grants:
            grouped_grants[key] = {}
        grouped_grants[key][grant_info.field] = grant_info


    # Prepare data for CSV
    csv_data = []

    for (trustfund_id, fiscal_year_id), grant_fields in grouped_grants.items():
        try:
            # Reconstruct the grant info from long format fields
            reconstructed_grant = type('GrantInfo', (), {
                'trustfund_id': trustfund_id,
                'fiscal_year_id': fiscal_year_id
            })()

            # Extract field values from long format
            country = grant_fields.get('country').value if 'country' in grant_fields else ''
            region_id = grant_fields.get('region_id').value if 'region_id' in grant_fields else None
            p_code_instrument = grant_fields.get('p_code_instrument').value if 'p_code_instrument' in grant_fields else ''
            p_code_description = grant_fields.get('p_code_description').value if 'p_code_description' in grant_fields else ''
            f4d_association = grant_fields.get('f4d_association').value if 'f4d_association' in grant_fields else None
            pillars = grant_fields.get('pillars').value if 'pillars' in grant_fields else ''
            ccts = grant_fields.get('ccts').value if 'ccts' in grant_fields else ''
            
            # Parse JSON fields
            pillar_explanations_str = grant_fields.get('pillar_explanations').value if 'pillar_explanations' in grant_fields else '{}'
            cct_explanations_str = grant_fields.get('cct_explanations').value if 'cct_explanations' in grant_fields else '{}'
            operations_str = grant_fields.get('operations').value if 'operations' in grant_fields else '{}'
            cpfs_str = grant_fields.get('cpfs').value if 'cpfs' in grant_fields else '{}'
            custom_indicators_str = grant_fields.get('custom_indicators').value if 'custom_indicators' in grant_fields else '{}'
            
            # Parse other fields
            challenges = grant_fields.get('challenges').value if 'challenges' in grant_fields else ''
            strategic_objective = grant_fields.get('strategic_objective').value if 'strategic_objective' in grant_fields else ''
            overall_progress = grant_fields.get('overall_progress').value if 'overall_progress' in grant_fields else ''
            implementation_challenges = grant_fields.get('implementation_challenges').value if 'implementation_challenges' in grant_fields else ''
            public_communication_external = grant_fields.get('public_communication_external').value if 'public_communication_external' in grant_fields else ''
            public_communication_internal = grant_fields.get('public_communication_internal').value if 'public_communication_internal' in grant_fields else ''
            collaborations = grant_fields.get('collaborations').value if 'collaborations' in grant_fields else ''
            other_teams = grant_fields.get('other_teams').value if 'other_teams' in grant_fields else ''
            other_ifis = grant_fields.get('other_ifis').value if 'other_ifis' in grant_fields else ''
            other_orgs = grant_fields.get('other_orgs').value if 'other_orgs' in grant_fields else ''
            describe_collaboration = grant_fields.get('describe_collaboration').value if 'describe_collaboration' in grant_fields else ''
            lessons_learned = grant_fields.get('lessons_learned').value if 'lessons_learned' in grant_fields else ''
            
            # Check each field for None before evaluating
            pillar_explanations_dict = ast.literal_eval(pillar_explanations_str) if pillar_explanations_str and pillar_explanations_str != '{}' else {}
            cct_explanations_dict = ast.literal_eval(cct_explanations_str) if cct_explanations_str and cct_explanations_str != '{}' else {}
            operations_dict = ast.literal_eval(operations_str) if operations_str and operations_str != '{}' else {}
            cpfs_dict = ast.literal_eval(cpfs_str) if cpfs_str and cpfs_str != '{}' else {}
            print(custom_indicators_str)
            custom_indicators_dict = ast.literal_eval(custom_indicators_str) if custom_indicators_str and custom_indicators_str != '{}' else {}

            region_name = ''
            if region_id:
                region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                if region:
                    region_name = region.region

            trustfund_name = ''
            ttl_name = ''
            if reconstructed_grant.trustfund_id:
                tf = session.query(TrustFund).filter_by(id=reconstructed_grant.trustfund_id, deleted=False).first()
                if tf:
                    trustfund_name = tf.name
                    ttl_name = tf.ttl if tf.ttl else ''

            fiscal_year = ''
            if reconstructed_grant.fiscal_year_id:
                fy = session.query(FiscalYear).filter_by(id=reconstructed_grant.fiscal_year_id, deleted=False).first()
                if fy:
                    fiscal_year = fy.fy

            row = {
                "trustfund": trustfund_name,
                "ttl": ttl_name if ttl_name else '',
                "fiscal_year": fiscal_year,
                "country": country,
                "p_code_instrument": p_code_instrument,
                "p_code_description": p_code_description,
                "f4d_association":  (
                    F4DAssociationEnum(f4d_association).value
                    if f4d_association is not None else None
                ),
                "region": region_name if region_name else '',
                "pillars": pillars if pillars else '',
                "ccts": ccts if ccts else '',
                "pillar_1_explanation": pillar_explanations_dict.get("Pillar 1: Strengthening Financial Sector Resiliency", ""),
                "pillar_2_explanation": pillar_explanations_dict.get("Pillar 2: Financing the Poor and Vulnerable", ""),
                "pillar_3_explanation": pillar_explanations_dict.get("Pillar 3: Financing the Real Economy", ""),
                "pillar_4_explanation": pillar_explanations_dict.get("Pillar 4: Developing Financial Markets", ""),
                "cct_explanation_1": cct_explanations_dict.get("Climate change and sustainable finance", ""),
                "cct_explanation_2": cct_explanations_dict.get("Advancing digitalization", ""),
                "cct_explanation_3": cct_explanations_dict.get("Financing solutions to close gender gaps", ""),
                "challenges": challenges,
                "strategic_objective": strategic_objective,
                "overall_progress": overall_progress,
                "implementation_challenges": implementation_challenges,
                "public_communication_external": public_communication_external,
                "public_communication_internal": public_communication_internal,
                "collaborations": collaborations,
                "other_teams": other_teams,
                "other_ifis": other_ifis,
                "other_orgs": other_orgs,
                "describe_collaboration": describe_collaboration,
                "lessons_learned": lessons_learned

            }
            # Handle operations dynamically
            if operations_dict:
                for key, value in operations_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            row[f"operation_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"operation_{nested_key}_{key}" not in headers:
                                headers.append(f"operation_{nested_key}_{key}")

            # Handle CPFS dynamically
            if cpfs_dict:
                for key, value in cpfs_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            row[f"cpf_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"cpf_{nested_key}_{key}" not in headers:
                                headers.append(f"cpf_{nested_key}_{key}")

            indicators = session.query(Indicator).filter(
                Indicator.team_id == team_id, Indicator.deleted == False).all()

            indicator_name_map = {
                indicator.id: {
                    "standard_name": indicator.standard_indicator_name,
                    "custom_name": indicator.indicator_name,
                    "indicator_conversion": indicator.indicator_conversion
                } for indicator in indicators
            }

            # Handle indicators dynamically
            if custom_indicators_dict:
                for key, value in custom_indicators_dict.items():
                    if key and isinstance(value, dict):
                        # Get standard and custom names from the mapping
                        indicator_info = indicator_name_map.get(
                            int(key), {"standard_name": "", "custom_name": "", "indicator_conversion": ""})
                        standard_indicator_name = indicator_info["standard_name"]
                        custom_indicator_name = indicator_info["custom_name"]
                        indicator_conversion = indicator_info["indicator_conversion"]

                        # Access the nested value directly from `value`
                        indicator_info = value

                        # Ensure deliverable_info is a dictionary
                        if isinstance(indicator_info, dict):
                            # Create a new row for each indicator
                            indicator_row = row.copy()  # Copy the base row
                            indicator_row["indicator_name"] = custom_indicator_name
                            indicator_row["standard_indicator_name"] = standard_indicator_name
                            indicator_row["indicator_conversion"] = indicator_conversion
                            indicator_row["indicator_input_value"] = indicator_info.get(
                                "input_value", "")
                            indicator_row["indicator_baseline_value"] = indicator_info.get(
                                "baseline_value", "")
                            indicator_row["indicator_year_baseline"] = indicator_info.get(
                                "year_baseline", "")
                            indicator_row["indicator_progress"] = indicator_info.get(
                                "progress", "")
                            indicator_row["indicator_target_value"] = indicator_info.get(
                                "target_value", "")
                            indicator_row["indicator_year_target"] = indicator_info.get(
                                "year_target", "")
                            indicator_row["indicator_data_collection"] = indicator_info.get(
                                "data_collection", "")
                            indicator_row["indicator_level_of_result"] = indicator_info.get(
                                "level_of_result", "")

                            # Append the indicator row to csv_data
                            csv_data.append(indicator_row)

        except Exception as e:
            print(f"Error processing grant info id {grant_info.id}: {e}")

    # Write data to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for data in csv_data:
            writer.writerow(data)
        st.success("Data have been exported!")

    # Read the CSV file to provide for download
    with open(filename, "rb") as f:
        csv_file = f.read()

    # Use st.download_button to allow file download
    st.download_button(
        label="Download CSV",
        data=csv_file,
        file_name=filename,
        mime='text/csv'
    )

    # Delete the file after download
    os.remove(filename)


def export_all_grants_deliverable(session, filename, team_id):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "ttl", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "deliverable_id", "deliverable_name", "standard_indicator_name", "indicator_conversion", "deliverable_input_value", "deliverable_progress", "deliverable_description", "deliverable_data_source", "deliverable_next_steps", "deliverable_supporting_materials_url"
    ]

    # Fetch all TrustFundIndicatorMapping records for the team with deliverables (custom_indicator = False)
    trustfund_mappings = session.query(TrustFundIndicatorMapping)\
        .join(Indicator, TrustFundIndicatorMapping.indicator_id == Indicator.id)\
        .filter(
            TrustFundIndicatorMapping.team_id == team_id,
            TrustFundIndicatorMapping.deleted == False,
            Indicator.custom_indicator == False,  # Only deliverables
            Indicator.deleted == False
        ).all()

    # Get unique trustfunds from the mappings
    trustfund_ids = list(set([mapping.trustfund_id for mapping in trustfund_mappings]))
    
    # Fetch trustfund details
    trustfunds = session.query(TrustFund).filter(
        TrustFund.id.in_(trustfund_ids),
        TrustFund.deleted == False
    ).all() if trustfund_ids else []

    # Create trustfund lookup
    trustfund_lookup = {tf.id: tf for tf in trustfunds}

    # Fetch all fiscal years for context
    fiscal_years = session.query(FiscalYear).filter(FiscalYear.deleted == False).all()
    fiscal_year_lookup = {fy.id: fy for fy in fiscal_years}

    # Fetch all regions for context
    regions = session.query(Region).filter(Region.deleted == False).all()
    region_lookup = {region.id: region for region in regions}

    # Fetch grant information to populate grant-specific fields
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, 
        GrantInfo.deleted == False
    ).all()
    
    # Group records by trustfund_id and fiscal_year_id to reconstruct wide format (like the working code)
    grouped_grants = {}
    for grant_info in grant_infos:
        key = (grant_info.trustfund_id, grant_info.fiscal_year_id)
        if key not in grouped_grants:
            grouped_grants[key] = {}
        grouped_grants[key][grant_info.field] = grant_info

    # Prepare data for CSV
    csv_data = []

    # Group mappings by trustfund for better organization
    trustfund_mappings_grouped = {}
    for mapping in trustfund_mappings:
        if mapping.trustfund_id not in trustfund_mappings_grouped:
            trustfund_mappings_grouped[mapping.trustfund_id] = []
        trustfund_mappings_grouped[mapping.trustfund_id].append(mapping)

    for trustfund_id, mappings in trustfund_mappings_grouped.items():
        try:
            # Get trustfund details
            trustfund = trustfund_lookup.get(trustfund_id)
            if not trustfund:
                continue

            trustfund_name = trustfund.name
            ttl_name = trustfund.ttl if trustfund.ttl else ''

            
            for fiscal_year_id, fiscal_year in fiscal_year_lookup.items():
              # Get grant fields for this trustfund and fiscal year (using the working logic)
                grant_fields = grouped_grants.get((trustfund_id, fiscal_year_id), {})
                
                # # Skip if no grant info and no mappings for this combination
                # if not grant_fields and not mappings:
                #     continue

               # Extract field values from long format (adapted from working code)
                country = grant_fields.get('country').value if 'country' in grant_fields else ''
                region_id = grant_fields.get('region_id').value if 'region_id' in grant_fields else None
                p_code_instrument = grant_fields.get('p_code_instrument').value if 'p_code_instrument' in grant_fields else ''
                p_code_description = grant_fields.get('p_code_description').value if 'p_code_description' in grant_fields else ''
                f4d_association = grant_fields.get('f4d_association').value if 'f4d_association' in grant_fields else None
                pillars = grant_fields.get('pillars').value if 'pillars' in grant_fields else ''
                ccts = grant_fields.get('ccts').value if 'ccts' in grant_fields else ''
                
                # Parse JSON fields (adapted from working code)
                pillar_explanations_str = grant_fields.get('pillar_explanations').value if 'pillar_explanations' in grant_fields else '{}'
                cct_explanations_str = grant_fields.get('cct_explanations').value if 'cct_explanations' in grant_fields else '{}'
                deliverables_str = grant_fields.get('deliverables').value if 'deliverables' in grant_fields else '{}'
                
                # Parse other fields
                challenges = grant_fields.get('challenges').value if 'challenges' in grant_fields else ''
                strategic_objective = grant_fields.get('strategic_objective').value if 'strategic_objective' in grant_fields else ''
                overall_progress = grant_fields.get('overall_progress').value if 'overall_progress' in grant_fields else ''
                implementation_challenges = grant_fields.get('implementation_challenges').value if 'implementation_challenges' in grant_fields else ''
                public_communication_external = grant_fields.get('public_communication_external').value if 'public_communication_external' in grant_fields else ''
                public_communication_internal = grant_fields.get('public_communication_internal').value if 'public_communication_internal' in grant_fields else ''
                collaborations = grant_fields.get('collaborations').value if 'collaborations' in grant_fields else ''
                other_teams = grant_fields.get('other_teams').value if 'other_teams' in grant_fields else ''
                other_ifis = grant_fields.get('other_ifis').value if 'other_ifis' in grant_fields else ''
                other_orgs = grant_fields.get('other_orgs').value if 'other_orgs' in grant_fields else ''
                describe_collaboration = grant_fields.get('describe_collaboration').value if 'describe_collaboration' in grant_fields else ''
                lessons_learned = grant_fields.get('lessons_learned').value if 'lessons_learned' in grant_fields else ''
                
                # Parse JSON fields safely (adapted from working code)
                import ast
                try:
                    pillar_explanations_dict = ast.literal_eval(pillar_explanations_str) if pillar_explanations_str and pillar_explanations_str != '{}' else {}
                    cct_explanations_dict = ast.literal_eval(cct_explanations_str) if cct_explanations_str and cct_explanations_str != '{}' else {}
                    deliverables_dict = ast.literal_eval(deliverables_str) if deliverables_str and deliverables_str != '{}' else {}
                except (ValueError, SyntaxError):
                    pillar_explanations_dict = {}
                    cct_explanations_dict = {}
                    deliverables_dict = {}

                # Get region name
                region_name = ''
                if region_id:
                    region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                    if region:
                        region_name = region.region

                # Create a base row with trustfund and grant info
                base_row = {
                    "trustfund": trustfund_name,
                    "ttl": ttl_name,
                    "fiscal_year": fiscal_year.fy,
                    "country": country,
                    "p_code_instrument": p_code_instrument,
                    "p_code_description": p_code_description,
                    "f4d_association": (
                        F4DAssociationEnum(f4d_association).value
                        if f4d_association is not None else ""
                    ),
                    "region": region_name,
                    "pillars": pillars,
                    "ccts": ccts,
                    "pillar_1_explanation": pillar_explanations_dict.get("Pillar 1: Strengthening Financial Sector Resiliency", ""),
                    "pillar_2_explanation": pillar_explanations_dict.get("Pillar 2: Financing the Poor and Vulnerable", ""),
                    "pillar_3_explanation": pillar_explanations_dict.get("Pillar 3: Financing the Real Economy", ""),
                    "pillar_4_explanation": pillar_explanations_dict.get("Pillar 4: Developing Financial Markets", ""),
                    "cct_explanation_1": cct_explanations_dict.get("Climate change and sustainable finance", ""),
                    "cct_explanation_2": cct_explanations_dict.get("Advancing digitalization", ""),
                    "cct_explanation_3": cct_explanations_dict.get("Financing solutions to close gender gaps", ""),
                    "challenges": challenges,
                    "strategic_objective": strategic_objective,
                    "overall_progress": overall_progress,
                    "implementation_challenges": implementation_challenges,
                    "public_communication_external": public_communication_external,
                    "public_communication_internal": public_communication_internal,
                    "collaborations": collaborations,
                    "other_teams": other_teams,
                    "other_ifis": other_ifis,
                    "other_orgs": other_orgs,
                    "describe_collaboration": describe_collaboration,
                    "lessons_learned": lessons_learned
                }

                # Create a row for each deliverable indicator mapped to this trustfund
                for mapping in mappings:
                    indicator = mapping.indicator
                    
                    # Create a new row for each deliverable
                    deliverable_row = base_row.copy()
                    
                    # Set deliverable info from indicator
                    deliverable_row["deliverable_id"] = indicator.indicator_id if indicator.indicator_id else ""
                    deliverable_row["deliverable_name"] = indicator.indicator_name if indicator.indicator_name else ""
                    deliverable_row["standard_indicator_name"] = indicator.standard_indicator_name if indicator.standard_indicator_name else ""
                    deliverable_row["indicator_conversion"] = indicator.indicator_conversion if indicator.indicator_conversion else ""
                    
                    # Get deliverable data from the deliverables JSON using indicator ID
                    deliverable_info = {}
                    if deliverables_dict and str(indicator.id) in deliverables_dict:
                        deliverable_data = deliverables_dict[str(indicator.id)]
                        if isinstance(deliverable_data, dict):
                            deliverable_info = deliverable_data
                    
                    # Extract deliverable values from JSON data
                    deliverable_row["deliverable_input_value"] = deliverable_info.get("input_value", "")
                    deliverable_row["deliverable_progress"] = deliverable_info.get("progress", "")
                    deliverable_row["deliverable_description"] = deliverable_info.get("description", "")
                    deliverable_row["deliverable_data_source"] = deliverable_info.get("data_source", "")
                    deliverable_row["deliverable_next_steps"] = deliverable_info.get("next_steps", "")
                    deliverable_row["deliverable_supporting_materials_url"] = deliverable_info.get("supporting_materials_url", "")
                    
                    # Append the deliverable row to csv_data
                    csv_data.append(deliverable_row)

        except Exception as e:
            print(f"Error processing trustfund {trustfund_id}: {e}")

    # If no mappings found, create at least one row to show the structure
    if not csv_data:
        empty_row = {header: "" for header in headers}
        csv_data.append(empty_row)

    # Write data to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for data in csv_data:
            writer.writerow(data)
        st.success("Data have been exported!")

    # Read the CSV file to provide for download
    with open(filename, "rb") as f:
        csv_file = f.read()

    # Use st.download_button to allow file download
    st.download_button(
        label="Download CSV",
        data=csv_file,
        file_name=filename,
        mime='text/csv'
    )

    # Delete the file after download
    os.remove(filename)


def export_all_grants_indicator(session, filename, team_id):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "ttl", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "indicator_id", "indicator_name", "standard_indicator_name", "indicator_conversion", "indicator_input_value", "indicator_baseline_value", "indicator_year_baseline", "indicator_progress", "indicator_target_value", "indicator_year_target", "indicator_data_collection", "indicator_level_of_result"
    ]

    # Fetch all TrustFundIndicatorMapping records for the team with indicators (custom_indicator = True)
    trustfund_mappings = session.query(TrustFundIndicatorMapping)\
        .join(Indicator, TrustFundIndicatorMapping.indicator_id == Indicator.id)\
        .filter(
            TrustFundIndicatorMapping.team_id == team_id,
            TrustFundIndicatorMapping.deleted == False,
            Indicator.custom_indicator == True,  # Only custom indicators
            Indicator.deleted == False
        ).all()

    # Get unique trustfunds from the mappings
    trustfund_ids = list(set([mapping.trustfund_id for mapping in trustfund_mappings]))
    
    # Fetch trustfund details
    trustfunds = session.query(TrustFund).filter(
        TrustFund.id.in_(trustfund_ids),
        TrustFund.deleted == False
    ).all() if trustfund_ids else []

    # Create trustfund lookup
    trustfund_lookup = {tf.id: tf for tf in trustfunds}

    # Fetch all fiscal years for context
    fiscal_years = session.query(FiscalYear).filter(FiscalYear.deleted == False).all()
    fiscal_year_lookup = {fy.id: fy for fy in fiscal_years}

    # Fetch all regions for context
    regions = session.query(Region).filter(Region.deleted == False).all()
    region_lookup = {region.id: region for region in regions}

    # Fetch grant information to populate grant-specific fields
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, 
        GrantInfo.deleted == False
    ).all()
    
    # Group records by trustfund_id and fiscal_year_id to reconstruct wide format (like the working code)
    grouped_grants = {}
    for grant_info in grant_infos:
        key = (grant_info.trustfund_id, grant_info.fiscal_year_id)
        if key not in grouped_grants:
            grouped_grants[key] = {}
        grouped_grants[key][grant_info.field] = grant_info

    # Prepare data for CSV
    csv_data = []

    # Group mappings by trustfund for better organization
    trustfund_mappings_grouped = {}
    for mapping in trustfund_mappings:
        if mapping.trustfund_id not in trustfund_mappings_grouped:
            trustfund_mappings_grouped[mapping.trustfund_id] = []
        trustfund_mappings_grouped[mapping.trustfund_id].append(mapping)

    for trustfund_id, mappings in trustfund_mappings_grouped.items():
        try:
            # Get trustfund details
            trustfund = trustfund_lookup.get(trustfund_id)
            if not trustfund:
                continue

            trustfund_name = trustfund.name
            ttl_name = trustfund.ttl if trustfund.ttl else ''
            
            for fiscal_year_id, fiscal_year in fiscal_year_lookup.items():
                                # Get grant fields for this trustfund and fiscal year (using the working logic)
                grant_fields = grouped_grants.get((trustfund_id, fiscal_year_id), {})
                
                # Extract field values from long format (adapted from working code)
                country = grant_fields.get('country').value if 'country' in grant_fields else ''
                region_id = grant_fields.get('region_id').value if 'region_id' in grant_fields else None
                p_code_instrument = grant_fields.get('p_code_instrument').value if 'p_code_instrument' in grant_fields else ''
                p_code_description = grant_fields.get('p_code_description').value if 'p_code_description' in grant_fields else ''
                f4d_association = grant_fields.get('f4d_association').value if 'f4d_association' in grant_fields else None
                pillars = grant_fields.get('pillars').value if 'pillars' in grant_fields else ''
                ccts = grant_fields.get('ccts').value if 'ccts' in grant_fields else ''
                
                # Parse JSON fields (adapted from working code)
                pillar_explanations_str = grant_fields.get('pillar_explanations').value if 'pillar_explanations' in grant_fields else '{}'
                cct_explanations_str = grant_fields.get('cct_explanations').value if 'cct_explanations' in grant_fields else '{}'
                indicators_str = grant_fields.get('custom_indicators').value if 'custom_indicators' in grant_fields else '{}'
                
                # Parse other fields
                challenges = grant_fields.get('challenges').value if 'challenges' in grant_fields else ''
                strategic_objective = grant_fields.get('strategic_objective').value if 'strategic_objective' in grant_fields else ''
                overall_progress = grant_fields.get('overall_progress').value if 'overall_progress' in grant_fields else ''
                implementation_challenges = grant_fields.get('implementation_challenges').value if 'implementation_challenges' in grant_fields else ''
                public_communication_external = grant_fields.get('public_communication_external').value if 'public_communication_external' in grant_fields else ''
                public_communication_internal = grant_fields.get('public_communication_internal').value if 'public_communication_internal' in grant_fields else ''
                collaborations = grant_fields.get('collaborations').value if 'collaborations' in grant_fields else ''
                other_teams = grant_fields.get('other_teams').value if 'other_teams' in grant_fields else ''
                other_ifis = grant_fields.get('other_ifis').value if 'other_ifis' in grant_fields else ''
                other_orgs = grant_fields.get('other_orgs').value if 'other_orgs' in grant_fields else ''
                describe_collaboration = grant_fields.get('describe_collaboration').value if 'describe_collaboration' in grant_fields else ''
                lessons_learned = grant_fields.get('lessons_learned').value if 'lessons_learned' in grant_fields else ''
                
                # Parse JSON fields safely (adapted from working code)
                import ast
                try:
                    pillar_explanations_dict = ast.literal_eval(pillar_explanations_str) if pillar_explanations_str and pillar_explanations_str != '{}' else {}
                    cct_explanations_dict = ast.literal_eval(cct_explanations_str) if cct_explanations_str and cct_explanations_str != '{}' else {}
                    indicators_dict = ast.literal_eval(indicators_str) if indicators_str and indicators_str != '{}' else {}
                except (ValueError, SyntaxError):
                    pillar_explanations_dict = {}
                    cct_explanations_dict = {}
                    indicators_dict = {}

                # Get region name
                region_name = ''
                if region_id:
                    region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                    if region:
                        region_name = region.region


                # Create a base row with trustfund info and empty grant fields
                base_row = {
                    "trustfund": trustfund_name,
                    "ttl": ttl_name,
                    "fiscal_year": fiscal_year.fy,
                    "country": country,
                    "p_code_instrument": p_code_instrument,
                    "p_code_description": p_code_description,
                    "f4d_association": (
                        F4DAssociationEnum(f4d_association).value
                        if f4d_association is not None else ""
                    ),
                    "region": region_name,
                    "pillars": pillars,
                    "ccts": ccts,
                    "pillar_1_explanation": pillar_explanations_dict.get("Pillar 1: Strengthening Financial Sector Resiliency", ""),
                    "pillar_2_explanation": pillar_explanations_dict.get("Pillar 2: Financing the Poor and Vulnerable", ""),
                    "pillar_3_explanation": pillar_explanations_dict.get("Pillar 3: Financing the Real Economy", ""),
                    "pillar_4_explanation": pillar_explanations_dict.get("Pillar 4: Developing Financial Markets", ""),
                    "cct_explanation_1": cct_explanations_dict.get("Climate change and sustainable finance", ""),
                    "cct_explanation_2": cct_explanations_dict.get("Advancing digitalization", ""),
                    "cct_explanation_3": cct_explanations_dict.get("Financing solutions to close gender gaps", ""),
                    "challenges": challenges,
                    "strategic_objective": strategic_objective,
                    "overall_progress": overall_progress,
                    "implementation_challenges": implementation_challenges,
                    "public_communication_external": public_communication_external,
                    "public_communication_internal": public_communication_internal,
                    "collaborations": collaborations,
                    "other_teams": other_teams,
                    "other_ifis": other_ifis,
                    "other_orgs": other_orgs,
                    "describe_collaboration": describe_collaboration,
                    "lessons_learned": lessons_learned
                }

                # Create a row for each custom indicator mapped to this trustfund
                for mapping in mappings:
                    indicator = mapping.indicator
                    
                    # Create a new row for each indicator
                    indicator_row = base_row.copy()
                    
                    # Set indicator info from indicator
                    indicator_row["indicator_id"] = indicator.indicator_id if indicator.indicator_id else ""
                    indicator_row["indicator_name"] = indicator.indicator_name if indicator.indicator_name else ""
                    indicator_row["standard_indicator_name"] = indicator.standard_indicator_name if indicator.standard_indicator_name else ""
                    indicator_row["indicator_conversion"] = indicator.indicator_conversion if indicator.indicator_conversion else ""
                    
                    # Get indicator data from the indicators JSON using indicator ID
                    indicator_info = {}
                    if indicators_dict and str(indicator.id) in indicators_dict:
                        indicator_data = indicators_dict[str(indicator.id)]
                        if isinstance(indicator_data, dict):
                            indicator_info = indicator_data
                    
                    # Extract indicator values from JSON data
                    indicator_row["indicator_input_value"] = indicator_info.get("input_value", "")
                    indicator_row["indicator_baseline_value"] = indicator_info.get("baseline_value", "")
                    indicator_row["indicator_year_baseline"] = indicator_info.get("year_baseline", "")
                    indicator_row["indicator_progress"] = indicator_info.get("progress", "")
                    indicator_row["indicator_target_value"] = indicator_info.get("target_value", "")
                    indicator_row["indicator_year_target"] = indicator_info.get("year_target", "")
                    indicator_row["indicator_data_collection"] = indicator_info.get("data_collection", "")
                    indicator_row["indicator_level_of_result"] = indicator_info.get("level_of_result", "")
                    
                    
                    # Append the indicator row to csv_data
                    csv_data.append(indicator_row)

        except Exception as e:
            print(f"Error processing trustfund {trustfund_id}: {e}")

    # If no mappings found, create at least one row to show the structure
    if not csv_data:
        empty_row = {header: "" for header in headers}
        csv_data.append(empty_row)

    # Write data to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for data in csv_data:
            writer.writerow(data)
        st.success("Data have been exported!")

    # Read the CSV file to provide for download
    with open(filename, "rb") as f:
        csv_file = f.read()

    # Use st.download_button to allow file download
    st.download_button(
        label="Download CSV",
        data=csv_file,
        file_name=filename,
        mime='text/csv'
    )

    # Delete the file after download
    os.remove(filename)

def dashboards(team_id):
    st.success("#### Dashboards")
    session = create_session()

    # Fetch data from database
    trustfunds = session.query(TrustFund).filter(TrustFund.deleted == False).all()
    indicators = session.query(Indicator).filter(Indicator.deleted == False).all()
    custom_indicators = session.query(Indicator).filter(Indicator.deleted == False, Indicator.custom_indicator==True).all()
    deliverables = session.query(Indicator).filter(Indicator.deleted == False, Indicator.custom_indicator==False).all()
    grants_info = session.query(GrantInfo).filter(GrantInfo.deleted == False).all()

    # Convert to DataFrame for easier manipulation
    trustfunds_df = pd.DataFrame([(tf.id, tf.name, tf.project_type) for tf in trustfunds], columns=['ID', 'Name', 'Project Type'])
    indicators_df = pd.DataFrame([(ind.id, ind.indicator_name, ind.custom_indicator) for ind in indicators], columns=['ID', 'Indicator Name', 'Custom Indicator'])
    custom_indicators_df = pd.DataFrame([(ind.id, ind.indicator_name, ind.custom_indicator) for ind in custom_indicators], columns=['ID', 'Indicator Name', 'Custom Indicator'])
    deliverables_df = pd.DataFrame([(ind.id, ind.indicator_name, ind.custom_indicator) for ind in deliverables], columns=['ID', 'Indicator Name', 'Custom Indicator'])

    # Additional Metrics
    st.info("##### Key Metrics")

    total_grants = len(trustfunds_df)
    total_indicators = len(custom_indicators_df)
    total_deliverables = len(deliverables_df)

    # Function to create a colored box
    def create_colored_box(title, count, color):
        box_style = f"""
        <div style="flex: 1; background-color: {color}; height: 80px; border-radius: 2px; margin: 10px; text-align: center; color: white; display: flex; align-items: center; justify-content: center;">
            <h5>{title}: {count}</h5>
        </div>
        """
        return box_style

    # Container for boxes
    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: flex-end;">
        """, unsafe_allow_html=True)
 
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(create_colored_box("Total Grants", total_grants, "#4CAF50"), unsafe_allow_html=True)
    with col2:
        st.markdown(create_colored_box("Total Indicators", total_indicators, "#2196F3"), unsafe_allow_html=True)
    with col3:
        st.markdown(create_colored_box("Total Deliverables", total_deliverables, "#FF9800"), unsafe_allow_html=True)

    # Closing the container
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</br></br>", unsafe_allow_html=True)
    # Indicator Overview
    st.info("##### Indicators and Deliverables")

    # Pie Chart for Unit of Measurement
    unit_counts = indicators_df['Custom Indicator'].value_counts()
    # Mapping the index to custom names
    legend_mapping = {
        True: "Custom Indicator",
        False: "Deliverable",
    }

    # Create new names for the pie chart based on the mapping
    new_names = [legend_mapping.get(value, str(value)) for value in unit_counts.index]
    # Create the pie chart using Plotly Graph Objects
    fig2 = go.Figure(data=[go.Pie(
        labels=new_names,
        values=unit_counts.values,
        textinfo='label+value'  # Show label and count
    )])

    fig2.update_layout(title_text='Distribution of Indicators and Deliverables')
    st.plotly_chart(fig2)
    
    st.markdown("</br></br>", unsafe_allow_html=True)
    #Time Series Chart for Custom Indicators
    st.info("##### Custom Indicators")

    # Get all custom indicators data
    all_indicators_data = []

    # Query to get grant information
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, 
        GrantInfo.deleted == False, 
        GrantInfo.field == "custom_indicators").all()

    for grant_info in grant_infos:
        custom_indicators_dict = eval(str(grant_info.value)) if grant_info.value else {}
        
        if custom_indicators_dict:

            fiscal_year_label = f"{grant_info.fiscal_year}" if grant_info.fiscal_year else ""
            
            row = {
                "grant_id": grant_info.id,
                "trustfund": grant_info.trustfund.name if hasattr(grant_info, 'trustfund') and grant_info.trustfund else "",
                "fiscal_year": grant_info.fiscal_year,  # Keep numeric version for sorting
                "fiscal_year_label": fiscal_year_label,  # Add display label
                "team_id": team_id
            }
            
            for key, value in custom_indicators_dict.items():
                if key and isinstance(value, dict):
                    indicator_info = value
                    
                    if isinstance(indicator_info, dict):
                        indicator_row = row.copy()
                        indicator_row["indicator_id"] = key
                        
                        # Get indicator name from various possible sources
                        indicator_name = indicator_info.get("indicator_name", "")
                        
                        # If indicator_name is empty, try to get it from the database or use key
                        if not indicator_name:
                            indicator = session.query(Indicator).filter(Indicator.id == key, Indicator.custom_indicator==True).first()
                            if indicator:
                                indicator_name = indicator.indicator_name
                            else:
                                indicator_name = key
                        
                        indicator_row["indicator_name"] = indicator_name
                        indicator_row["input_value"] = indicator_info.get("input_value", "")
                        indicator_row["level_of_result"] = indicator_info.get("level_of_result", "")
                        indicator_row["progress"] = indicator_info.get("progress", "")
                        indicator_row["baseline_value"] = indicator_info.get("baseline_value", "")
                        indicator_row["year_baseline"] = indicator_info.get("year_baseline", "")    
                        indicator_row["target_value"] = indicator_info.get("target_value", "")
                        indicator_row["year_target"] = indicator_info.get("year_target", "")    

                        
                        all_indicators_data.append(indicator_row)

    # Convert to DataFrame
    if all_indicators_data:
        indicators_df = pd.DataFrame(all_indicators_data)
        
        st.write(f"Found data points for {int(len(indicators_df)/len(grant_infos))} indicator(s)")
        
        # Convert fiscal_year and indicator_input_value to numeric
        indicators_df["fiscal_year"] = pd.to_numeric(indicators_df["fiscal_year"], errors='coerce')
        indicators_df["input_value"] = pd.to_numeric(indicators_df["input_value"], errors='coerce')
        
        # Sort by fiscal year
        indicators_df = indicators_df.sort_values("fiscal_year")
        
        # Get unique indicator names for dropdown (non-empty values only)
        indicator_names = indicators_df["indicator_name"].dropna().unique().tolist()
        indicator_names = [name for name in indicator_names if name]  # Filter out empty strings
        
        if indicator_names:
            # Create dropdown selector for indicators
            selected_indicator = st.selectbox("Select Custom Indicator", indicator_names)
            
            # Filter data based on selected indicator
            filtered_data = indicators_df[indicators_df["indicator_name"] == selected_indicator]
            
            if not filtered_data.empty:
                # Create time series chart using fiscal_year_label for display
                fig = px.line(
                    filtered_data,
                    x="fiscal_year_label",  # Use the label instead of the numeric value
                    y="input_value",
                    markers=True,
                    title=f"{selected_indicator}"
                )
                
                # Ensure the x-axis maintains the correct order
                fig.update_xaxes(
                    categoryorder='array',
                    categoryarray=sorted(filtered_data["fiscal_year_label"].tolist(), 
                                        key=lambda x: pd.to_numeric(x.replace("FY ", ""), errors='coerce'))
                )
                
                fig.update_layout(
                    xaxis_title="Fiscal Year",
                    yaxis_title="Indicator Value",
                    legend_title="Legend"
                )
                
                st.plotly_chart(fig)
                
                # Add a data table below the chart - using the label in the display
                st.warning("###### Custom Indicators Data Table")
                display_df = filtered_data[["fiscal_year_label", "input_value", "level_of_result", 'baseline_value', 'year_baseline', "progress", 'target_value', 'year_target']].copy()
                display_df.columns = ["Fiscal Year", "Indicator Value", "Level of Result", "Baseline Value", "Year Baseline", "Progress", "Target Value", "Year Target"]
                display_df["Year Baseline"] = display_df["Year Baseline"].astype(str).str.replace("None", "")
                display_df["Year Target"] = display_df["Year Target"].astype(str).str.replace("None", "")
                st.dataframe(display_df, hide_index=True)
            else:
                st.warning("No data available for this indicator")
        else:
            st.warning("No indicator names found in the data")
    else:
        st.warning("No custom indicators data found")


    st.markdown("</br></br>", unsafe_allow_html=True)
    #Time Series Chart for Deliverables
    st.info("##### Deliverables")

    # Get all deliverables data
    all_deliverables_data = []

    # Query to get grant information
    grant_infos_deliverables = session.query(GrantInfo).filter(
    GrantInfo.team_id == team_id, 
    GrantInfo.deleted == False, 
    GrantInfo.field == "deliverables").all()

    for grant_info in grant_infos_deliverables:
        deliverables_dict = eval(str(grant_info.value)) if grant_info.value else {}
        
        if deliverables_dict:

            fiscal_year_label = f"{grant_info.fiscal_year}" if grant_info.fiscal_year else ""

            row = {
                "grant_id": grant_info.id,
                "trustfund": grant_info.trustfund.name if hasattr(grant_info, 'trustfund') and grant_info.trustfund else "",
                "fiscal_year": grant_info.fiscal_year, 
                "fiscal_year_label": fiscal_year_label,
                "team_id": team_id
            }
            
            for key, value in deliverables_dict.items():
                if key and isinstance(value, dict):
                    deliverable_info = value
                    
                    if isinstance(deliverable_info, dict):
                        indicator_row = row.copy()
                        indicator_row["indicator_id"] = key
                        
                        # Get indicator name from various possible sources
                        indicator_name = indicator_info.get("indicator_name", "")
                        
                        # If indicator_name is empty, try to get it from the database or use key
                        if not indicator_name:
                            indicator = session.query(Indicator).filter(Indicator.id == key, Indicator.custom_indicator==False).first()
                            if indicator:
                                indicator_name = indicator.indicator_name
                            else:
                                indicator_name = key
                        
                        indicator_row["indicator_name"] = indicator_name
                        indicator_row["input_value"] = deliverable_info.get("input_value", "")
                        indicator_row["progress"] = deliverable_info.get("progress", "")
                        indicator_row["description"] = deliverable_info.get("description", "")
                        indicator_row["data_source"] = deliverable_info.get("data_source", "")    
                        indicator_row["next_steps"] = deliverable_info.get("next_steps", "")
                        indicator_row["supporting_materials_url"] = deliverable_info.get("supporting_materials_url", "")    

                        
                        all_deliverables_data.append(indicator_row)

    # Convert to DataFrame
    if all_deliverables_data:
        deliverables_df = pd.DataFrame(all_deliverables_data)
        
        st.write(f"Found data points for {int(len(deliverables_df)/len(grant_infos))} deliverable(s)")
        
        # Convert fiscal_year and indicator_input_value to numeric
        deliverables_df["fiscal_year"] = pd.to_numeric(deliverables_df["fiscal_year"], errors='coerce')
        
        # Sort by fiscal year
        deliverables_df = deliverables_df.sort_values("fiscal_year")
        
        # Get unique indicator names for dropdown (non-empty values only)
        indicator_names = deliverables_df["indicator_name"].dropna().unique().tolist()
        indicator_names = [name for name in indicator_names if name]  # Filter out empty strings
        
        if indicator_names:
            
            # Create dropdown selector for indicators
            selected_deliverable = st.selectbox("Select Deliverable", indicator_names)

            # Filter data based on selected indicator
            filtered_deliverables_data = deliverables_df[deliverables_df["indicator_name"] == selected_deliverable]

            if not filtered_deliverables_data.empty:
                # Create a DataFrame to count occurrences of each status by fiscal year
                category_counts = filtered_deliverables_data.groupby(
                    ["fiscal_year_label", "input_value"]  # Assuming 'input_value' holds the categories
                ).size().reset_index(name='count')

                # Define custom colors for each status
                color_map = {
                    "Completed": "green",
                    "Not Started": "red",
                    "In Progress": "orange"
                }

                # Create a stacked bar chart for deliverable categories
                fig = px.bar(
                    category_counts,
                    x="fiscal_year_label",
                    y="count",
                    color="input_value",  # Differentiate the categories
                    title="Deliverable Categories Over Time",
                    barmode='stack',  # Stacking the bars
                    color_discrete_map=color_map,  # Use the custom color map
                    hover_data=None  # Hide hover text
                )

                # Update layout for better readability
                fig.update_layout(
                    xaxis_title="Fiscal Year",
                    #yaxis_title="Count of Deliverables",
                    yaxis_title="",  # Hide y-axis title
                    yaxis=dict(showticklabels=False),  # Hide y-axis tick labels
                    legend_title="Deliverable Status",
                    xaxis={'categoryorder': 'total descending'}  # Optional: order by total counts
                )

                # Display the chart in Streamlit
                st.plotly_chart(fig)
                
                # Add a data table below the chart - using the label in the display
                st.warning("###### Deliverables Data Table")
                display_deliverable_df = filtered_deliverables_data[["fiscal_year_label", "input_value", "progress", "description", 'data_source', 'next_steps', 'supporting_materials_url']].copy()
                display_deliverable_df.columns = ["Fiscal Year", "Deliverable Value", "Progress", "Description", "Data Source", "Next Steps", "Supporting Materials URL"]
                st.dataframe(display_deliverable_df, hide_index=True)
            else:
                st.warning("No data available for this deliverable")
        else:
            st.warning("No deliverable names found in the data")
    else:
        st.warning("No deliverables data found")

    # Close the session
    session.close()

if __name__ == "__main__":
    main()
