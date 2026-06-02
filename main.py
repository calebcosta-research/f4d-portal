import csv
import os
import time
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Enum, and_, create_engine
import streamlit as st
from connection import create_session
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from model import F4DAssociationEnum, FiscalYear, GrantInfo, Region, TrustFund, Indicator, Country, TrustFundIndicatorMapping, User
import pandas as pd
import datetime
import ast
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
st.set_page_config(page_title="F4D Results Reporting",
                   layout="centered")  # wide


def main():
    # Initialize session state for user login and user_id status
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    if "current_trustfund_id" not in st.session_state:
        st.session_state.current_trustfund_id = None
    if "current_fiscal_year_id" not in st.session_state:
        st.session_state.current_fiscal_year_id = None

    # Check if the user is logged in
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
            # Get user details only for non-admin login
            if username != super_admin_username:
                user = session.query(User).filter_by(username=username).first()
            else:
                user = None

            # Update session state on successful login
            st.session_state.logged_in = True
            st.session_state.user_id = user.id if user else None
            st.success("Logged in successfully!")
            st.session_state.current_trustfund_id = None
            st.session_state.current_fiscal_year_id = None
            st.rerun()
        else:
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
        return user.password == password

    except NoResultFound:
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


# Function to normalize values
def normalize(value):
    return value if value is not None else ""


def display_main_app():
    # Define pages with subpages
    pages = {
          "Home": [home, None],
          "Report new results": [new_grant, None],
          "Edit results": [all_grants, None],
          "Download results ": [download_grants, None],
    }
    
    # Map subpages for specific main pages
    subpages = {
        "Report new results": [
            "Basic Grant Information", 
            "Strategic Objective & Progress", 
            "Lending Operations", 
            "Collaboration/Partnership", 
            "Outputs/deliverables", 
            "Results Indicators"
        ]
    }
    
    # Initialize session state variables if they don't exist
    if 'current_main_page' not in st.session_state:
        st.session_state.current_main_page = "Home"
    if 'current_subpage' not in st.session_state:
        st.session_state.current_subpage = None
    if 'show_warning' not in st.session_state:
        st.session_state.show_warning = False
    if 'target_main_page' not in st.session_state:
        st.session_state.target_main_page = None
    if 'target_subpage' not in st.session_state:
        st.session_state.target_subpage = None
    if 'logout_requested' not in st.session_state:
        st.session_state.logout_requested = False
    if 'needs_rerun' not in st.session_state:
        st.session_state.needs_rerun = False
        
    # Define the unsaved changes mapping for each section
    unsaved_mapping = {
        "Basic Grant Information": 'grant_info_unsaved_changes',
        "Strategic Objective & Progress": 'strategic_objective_unsaved_changes',
        "Lending Operations": 'operations_unsaved_changes',
        "Collaboration/Partnership": 'collaboration_unsaved_changes',
        "Outputs/deliverables": 'deliverables_unsaved_changes',
        "Results Indicators": 'custom_indicators_unsaved_changes'
    }
    
    # Check for unsaved changes in current section
    has_unsaved_changes = False
    unsaved_section = None
    
    if st.session_state.current_main_page == "Report new results" and st.session_state.current_subpage in unsaved_mapping:
        state_key = unsaved_mapping[st.session_state.current_subpage]
        if st.session_state.get(state_key, False):
            unsaved_section = st.session_state.current_subpage
            has_unsaved_changes = True
    
    # Button callbacks
    def set_stay_on_page():
        st.session_state.show_warning = False
        st.session_state.logout_requested = False
        # Clear the target pages since we're staying
        st.session_state.target_main_page = None
        st.session_state.target_subpage = None
    
    def set_leave_without_saving():
        # Clear unsaved changes flag
        if st.session_state.current_main_page == "Report new results" and st.session_state.current_subpage in unsaved_mapping:
            st.session_state[unsaved_mapping[st.session_state.current_subpage]] = False
        
        st.session_state.show_warning = False
        
        if st.session_state.logout_requested:
            st.session_state.logged_in = False
            st.session_state.logout_requested = False
        else:
            # Only update if we have target pages set
            if st.session_state.target_main_page is not None:
                st.session_state.current_main_page = st.session_state.target_main_page
            if st.session_state.target_subpage is not None:
                st.session_state.current_subpage = st.session_state.target_subpage
            
            # Clear targets
            st.session_state.target_main_page = None
            st.session_state.target_subpage = None
    
    def set_logout():
        if has_unsaved_changes:
            st.session_state.show_warning = True
            st.session_state.logout_requested = True
        else:
            st.session_state.logged_in = False
    
    # Check if we need to perform a rerun from the previous interaction
    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()
    
    # Display username or title in sidebar
    st.sidebar.title(str(current_username()) + " - " + str(current_grantname()))

    
    # Main page selection - we use radio buttons without callbacks
    main_pages = list(pages.keys())
    
    # Always use current page index for radio button display
    display_main_index = main_pages.index(st.session_state.current_main_page)
    
    # Create unique key that includes warning state and timestamp to force refresh
    radio_key_suffix = f"{st.session_state.show_warning}_{st.session_state.target_main_page}_{id(st.session_state)}"
    radio_id = f"main_page_selector_{st.session_state.current_main_page}_{radio_key_suffix}"
    
    selected_main_page = st.sidebar.radio(
        "Select Main Page", 
        main_pages,
        index=display_main_index,
        key=radio_id
    )
    
    # Check if selection changed
    if selected_main_page != st.session_state.current_main_page:
        if not st.session_state.show_warning:  # Only process if not already showing warning
            if has_unsaved_changes:
                # Set the target page for when user confirms leaving
                st.session_state.target_main_page = selected_main_page
                st.session_state.target_subpage = None
                st.session_state.show_warning = True
                st.rerun()  # Rerun to show warning dialog
            else:
                # No unsaved changes, navigate directly
                st.session_state.current_main_page = selected_main_page
                st.session_state.current_subpage = None
                st.rerun()
    
    # Logout button
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("Logout", type="primary"):
            set_logout()
            if not has_unsaved_changes:
                st.success("Logged out successfully!")
                st.rerun()
            st.session_state.current_trustfund_id = None
            st.session_state.current_fiscal_year_id = None
            st.rerun()
    
    # Subpage selection (if applicable) - with collapsible expander
    if st.session_state.current_main_page in subpages:
        subpage_options = subpages[st.session_state.current_main_page]
        
        # Always use current subpage index for radio button display
        if st.session_state.current_subpage and st.session_state.current_subpage in subpage_options:
            display_sub_index = subpage_options.index(st.session_state.current_subpage)
        else:
            # If no subpage is selected yet, set it to the first one
            if st.session_state.current_subpage is None:
                st.session_state.current_subpage = subpage_options[0]
            display_sub_index = 0
        
        # Create collapsible expander for subpages
        # Auto-expand if we're on "Report new results" page or if showing warning
        is_expanded = (st.session_state.current_main_page == "Report new results" or 
                      st.session_state.show_warning)
        
        with st.sidebar.expander(
            f"📋 {st.session_state.current_main_page} Sections", 
            expanded=is_expanded
        ):
            # Create unique key that includes warning state and timestamp to force refresh
            subpage_key_suffix = f"{st.session_state.show_warning}_{st.session_state.target_subpage}_{id(st.session_state)}"
            subpage_radio_id = f"subpage_selector_{st.session_state.current_main_page}_{st.session_state.current_subpage}_{subpage_key_suffix}"
            
            selected_subpage = st.radio(
                "Select Section:",
                subpage_options,
                index=display_sub_index,
                key=subpage_radio_id
            )
        
        # Check if selection changed
        if selected_subpage != st.session_state.current_subpage:
            if not st.session_state.show_warning:  # Only process if not already showing warning
                if has_unsaved_changes:
                    # Set the target subpage for when user confirms leaving
                    st.session_state.target_main_page = st.session_state.current_main_page
                    st.session_state.target_subpage = selected_subpage
                    st.session_state.show_warning = True
                    st.rerun()  # Rerun to show warning dialog
                else:
                    # No unsaved changes, navigate directly
                    st.session_state.current_subpage = selected_subpage
                    st.rerun()
    else:
        selected_subpage = None
    
    # Handle warning for unsaved changes
    if st.session_state.show_warning:
        warning_message = "You have unsaved changes." if not unsaved_section else f"You have unsaved changes in the {unsaved_section} section."
        st.warning(f"{warning_message} What would you like to do?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Stay on this page"):
                set_stay_on_page()
                st.rerun()  # Rerun to hide warning and reset radio buttons
        with col2:
            if st.button("Leave without saving"):
                set_leave_without_saving()
                if st.session_state.logout_requested and not st.session_state.logged_in:
                    st.success("Logged out successfully!")
                st.rerun()
    
    # Render the selected page content (always render to preserve form data)
    current_main = st.session_state.current_main_page
    current_sub = st.session_state.current_subpage
    
    if current_main == "Home":
        home()
    elif current_main == "Report new results":
        _resolve_grant_context()
        if current_sub == "Basic Grant Information":
            basic_grant_info()
        elif current_sub == "Strategic Objective & Progress":
            strategic_objective_progress()
        elif current_sub == "Lending Operations":
            lending_operations()
        elif current_sub == "Collaboration/Partnership":
            collaboration_partnership()
        elif current_sub == "Outputs/deliverables":
            deliverables()
        elif current_sub == "Results Indicators":
            custom_indicators()
        else:
            basic_grant_info()
    elif current_main == "Edit results":
        all_grants()
    elif current_main == "Download results ":
        download_grants()
    else:
        st.error(f"Page '{current_main}' not found")


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


<<<<<<< HEAD
=======
def _resolve_grant_context():
    """Ensure current_trustfund_id and current_fiscal_year_id are set in session state.

    Called once before rendering any 'Report new results' section so that every
    section can rely on these values being populated without each one having to
    implement its own fallback logic.
    """
    tf_id = st.session_state.get("current_trustfund_id")
    fy_id = st.session_state.get("current_fiscal_year_id")

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
            saved_fy_rows = (
                session.query(GrantInfo.fiscal_year_id)
                .filter_by(trustfund_id=tf_id, deleted=False)
                .distinct()
                .all()
            )
            saved_fy_ids = [row[0] for row in saved_fy_rows if row[0] is not None]
            if len(saved_fy_ids) == 1:
                st.session_state.current_fiscal_year_id = saved_fy_ids[0]
            # If multiple years exist, leave fy_id as None; basic_grant_info's
            # switcher is the canonical place to choose between them.
    finally:
        session.close()


>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
def home():
    st.session_state.current_trustfund_id = None
    st.session_state.current_fiscal_year_id = None
    st.success("# F4D Results Reporting")
    st.write(
        """
This form aims to gather information on F4D financed activities for the F4D Annual Report. It will be used to record progress of the F4D umbrella, which is a mandatory donor reporting requirement. Note that the information in this form may be made public, hence please indicate clearly in case anything reported here should be treated confidentially. \n
TTLs of F4D grants are requested to review the pre-filled sections and to insert requested information. For any questions reach out to: F4DUmbrella@worldbank.org \n

""")
    
    st.write("""
             <h2>Instructions for Using the F4D Results Reporting</h2>
<h5>Pages and Sections</h5>
The application is organized into multiple pages, one of them containing specific sections (subpages) to help you manage grant information effectively.
             <p></p>

<u>Home:</u> Overview and instruction.<br/>
<u>Report new results:</u> Where you can enter and manage grant details.<br/>
<i>Basic Grant Information:</i> Enter basic details about the grant.<br/>
<i>Strategic Objective & Progress:</i> Define the strategic objectives and progress of the grant.<br/>
<i>Lending Operations:</i> Manage lending operations related to the grant.<br/>
<i>Collaboration/Partnership:</i> Manage collaboration and partnership details.<br/>
<i>Outputs/deliverables:</i> Enter and manage outputs and deliverables.<br/>
<i>Results Indicators:</i> Define and manage results indicators for the grant.<br/>
<u>Edit results:</u> View and edit existing grants.<br/>
<u>Download results:</u> Download grant data in CSV formats.<br/>

             
<h5>Important Notes</h5>
Single Record Saving: You can only save one record for each combination of Grant ID and fiscal year. Ensure that the details are correct before saving.<br/>
Data Protection: Make sure to save your results frequently to avoid losing any data. Click the “Save” button regularly.<br/>

<p></p>             
<h5>Session Management</h5>
Navigating Between Sections: You can navigate between sections without losing your data. Your session will remain active, and all entered data will be retained.<br/>
Navigating Between Pages: Be cautious when switching between different pages, as this will reset your session and you may lose any unsaved data.<br/>

<p></p>               
<h5>User Association</h5>
Each Grant ID is associated with a single user. This ensures that data entry remains organized and unique to each user.<br/>

<p></p>
<h5>Troubleshooting</h5>
If you encounter any bugs or errors while using the application, please contact fkurbonov1@worldbank.org for assistance.<br/>
<p></p>
             """, unsafe_allow_html=True)

    # Display the current user's username
    st.write(f"**Current User:** {current_username()}")
    
    # Display the current grant name
    st.write(f"**Current Grant Name:** {current_grantname()}")


def basic_grant_info():
    st.success("### 1. Basic Grant Information")
    data = read_data()

    session = create_session()

    print(st.session_state.current_trustfund_id, st.session_state.current_fiscal_year_id)

<<<<<<< HEAD
    existing_grant_info = session.query(GrantInfo).filter_by(
        trustfund_id=st.session_state.current_trustfund_id,
        fiscal_year_id=st.session_state.current_fiscal_year_id
    ).first()
=======
    # Resolve the effective trustfund_id — session state may be None if user came from Home
    effective_trustfund_id = st.session_state.current_trustfund_id or current_trustfund_id()

    # Sync trustfund_id into session state if it was missing
    if effective_trustfund_id and not st.session_state.current_trustfund_id:
        st.session_state.current_trustfund_id = effective_trustfund_id

    # Find all distinct fiscal years that have saved data for this trustfund
    saved_fy_rows = (
        session.query(GrantInfo.fiscal_year_id)
        .filter_by(trustfund_id=effective_trustfund_id, deleted=False)
        .distinct()
        .all()
    )
    saved_fy_ids = [row[0] for row in saved_fy_rows if row[0] is not None]

    # Build a mapping of fy label → id for the fiscal years that have saved data
    saved_fy_options = [(fy_label, fy_id) for fy_label, fy_id in data["fiscal_years"] if fy_id in saved_fy_ids]

    # Show a fiscal year switcher when more than one year of data exists
    if len(saved_fy_options) > 1:
        fy_labels = [opt[0] for opt in saved_fy_options]
        current_fy_id = st.session_state.current_fiscal_year_id
        current_fy_index = next((i for i, opt in enumerate(saved_fy_options) if opt[1] == current_fy_id), 0)

        def _on_fy_switch():
            selected_label = st.session_state["_fy_switcher"]
            st.session_state.current_fiscal_year_id = next(
                (opt[1] for opt in saved_fy_options if opt[0] == selected_label), None
            )
            # Clear cached initial values so the form reloads for the new year
            st.session_state.pop("grant_info_initial_values", None)

        st.selectbox(
            "Select fiscal year to edit:",
            fy_labels,
            index=current_fy_index,
            key="_fy_switcher",
            on_change=_on_fy_switch,
        )
        # Ensure current_fiscal_year_id matches the switcher selection
        if st.session_state.current_fiscal_year_id is None and saved_fy_options:
            st.session_state.current_fiscal_year_id = saved_fy_options[0][1]
    elif len(saved_fy_options) == 1 and st.session_state.current_fiscal_year_id is None:
        st.session_state.current_fiscal_year_id = saved_fy_options[0][1]

    # Load the existing record for the currently selected fiscal year
    if st.session_state.current_fiscal_year_id is not None:
        existing_grant_info = session.query(GrantInfo).filter_by(
            trustfund_id=effective_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            deleted=False
        ).first()
    else:
        existing_grant_info = None
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)

    # Initialize variables
    trustfund_id, fiscal_year_id = None, None
    country, p_code_instrument, p_code_description, f4d_association = [], None, None, None
    region_id, pillars, ccts, pillar_explanations, cct_explanations = None, [], [], {}, {}

    # If existing data is found, populate the variables with that data
    if existing_grant_info:
        print("Existing grant info found:", existing_grant_info)
        trustfund_id = existing_grant_info.trustfund_id
        fiscal_year_id = existing_grant_info.fiscal_year_id

        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=trustfund_id,
            fiscal_year_id=fiscal_year_id,
            deleted=False
        ).all()

        for entry in long_format_entries:
            if entry.field == "p_code_instrument":
                p_code_instrument = entry.value
            elif entry.field == "country":
                country = entry.value.split(', ') if entry.value else []
            elif entry.field == "p_code_description":
                p_code_description = entry.value
            elif entry.field == "f4d_association":
                f4d_association = entry.value
            elif entry.field == "region_id":
                region_id = int(entry.value) if entry.value else None
            elif entry.field == "pillars":
                pillars = entry.value.split(', ') if entry.value else []
            elif entry.field == "ccts":
                ccts = entry.value.split(', ') if entry.value else []
            elif entry.field == "pillar_explanations":
                pillar_explanations = ast.literal_eval(entry.value) if entry.value else {}
            elif entry.field == "cct_explanations":
                cct_explanations = ast.literal_eval(entry.value) if entry.value else {}

    print(st.session_state.grant_info_initial_values if "grant_info_initial_values" in st.session_state else "No initial values set")
    # Store initial values in session state for change detection
    if "grant_info_initial_values" not in st.session_state:
        st.session_state.grant_info_initial_values = {
            "fiscal_year_id": fiscal_year_id,
            "p_code_instrument": p_code_instrument,
            "country": country,
            "p_code_description": p_code_description,
            "f4d_association": f4d_association,
            "region_id": region_id,
            "pillars": pillars,
            "ccts": ccts,
            "pillar_explanations": pillar_explanations,
            "cct_explanations": cct_explanations
        }
        st.session_state.grant_info_unsaved_changes = False
    else:
        # Update initial values if they already exist
        st.session_state.grant_info_initial_values.update({
            "fiscal_year_id": fiscal_year_id,
            "p_code_instrument": p_code_instrument,
            "country": country,
            "p_code_description": p_code_description,
            "f4d_association": f4d_association,
            "region_id": region_id,
            "pillars": pillars,
            "ccts": ccts,
            "pillar_explanations": pillar_explanations,
            "cct_explanations": cct_explanations
        })

    # Grant Name Input
    grant_name = st.text_input(
        "Grant ID - Grant Name: *",
        value=existing_grant_info.trustfund.name if existing_grant_info else data["trustfunds"][0][0],
        disabled=True
    )

    # Extract trustfund_id based on the selection
    for tf in data["trustfunds"]:
        if tf[0] == grant_name:
            trustfund_id = tf[1]
            break

    # Fiscal Year Selection
    fiscal_year = st.selectbox("Fiscal Year: *",
                                [option[0] for option in data["fiscal_years"]],
                                index=None if not fiscal_year_id else next(
                                    (i for i, option in enumerate(data["fiscal_years"]) if option[1] == fiscal_year_id), None))

    # Update fiscal_year_id
    fiscal_year_id = next((fy[1] for fy in data["fiscal_years"] if fy[0] == fiscal_year), None)

    # P Code Instrument Selection
    p_code_instrument = st.selectbox(
        "Product line/instrument: *", 
        ["ASA", "IPF", "PforR", "DPF", "Other"], 
        index=["ASA", "IPF", "PforR", "DPF", "Other"].index(p_code_instrument) if p_code_instrument in ["ASA", "IPF", "PforR", "DPF", "Other"] else None
    )

    # Handle "Other" selection
    if p_code_instrument == "Other":
        p_code_description = st.text_input("If other, please describe:", value=p_code_description or "")
    else:
        p_code_description = None

    # F4D Association Radio
    f4d_association_value = st.radio(
        "Is the P code only associated with this F4D grant? *",
        ["Yes, this P code is used solely for F4D funded activities",
         "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well."],
        index=None if not f4d_association else ["Yes, this P code is used solely for F4D funded activities",
                                                 "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well."].index(f4d_association)
    )

    # Set F4D Association Enum
    if f4d_association_value == "Yes, this P code is used solely for F4D funded activities":
        f4d_association = F4DAssociationEnum.SOLELY_F4D
    elif f4d_association_value == "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well.":
        f4d_association = F4DAssociationEnum.OTHER_FUNDING
    else:
        f4d_association = None


    # Region Selection
    region = st.selectbox("Region: *",
                            [option[0] for option in data["regions"]],
                            index=None if not region_id else next(
                                (i for i, option in enumerate(data["regions"]) if option[1] == region_id), None))
    # Update region_id
    if region:
        region_id = next((r[1] for r in data["regions"] if r[0] == region), None)


    # Country Selection
    default_countries = country.split(', ') if isinstance(country, str) else country or []
    country = st.multiselect("Country (multiple choice): *", sorted([c[0] for c in data["countries"]]), default=default_countries)

    # Pillars Selection
    pillars = st.multiselect("Select the pillar(s) this grant contributes to (multiple choice): *",
                             ["Pillar 1: Strengthening Financial Sector Resiliency",
                              "Pillar 2: Financing the Poor and Vulnerable",
                              "Pillar 3: Financing the Real Economy",
                              "Pillar 4: Developing Financial Markets"],
                             default=pillars)

    # Explanations
    for pillar in pillars:
        explanation = st.text_area(f"Explain how it contributes to {pillar}", key=pillar, value=pillar_explanations.get(pillar, ""))
        pillar_explanations[pillar] = explanation

    # CCTs Selection
    ccts = st.multiselect("Select the cross-cutting theme(s) this grant contributes to and explain how (multiple choice):", 
                          ["Climate change and sustainable finance", 
                           "Advancing digitalization", 
                           "Financing solutions to close gender gaps"],
                          default=ccts)

    # CCT Explanations
    for cct in ccts:
        explanation = st.text_area(f"Explain how it contributes to {cct}", key=cct, value=cct_explanations.get(cct, ""))
        cct_explanations[cct] = explanation

    # Check for changes
    current_values = {
        "fiscal_year_id": fiscal_year_id,
        "p_code_instrument": p_code_instrument,
        "country": country,
        "p_code_description": p_code_description,
        "f4d_association": f4d_association.value if isinstance(f4d_association, F4DAssociationEnum) else f4d_association,
        "region_id": region_id,
        "pillars": pillars or [],
        "ccts": ccts or [],
        "pillar_explanations": pillar_explanations or {},
        "cct_explanations": cct_explanations or {}
    }

    # Change detection
    changes_detected = any(current_values[key] != st.session_state.grant_info_initial_values.get(key) for key in current_values)

    # Update session state for unsaved changes
    st.session_state.grant_info_unsaved_changes = changes_detected

    # Mandatory fields check
    mandatory_fields = [
        (grant_name, 'Grant ID - Grant Name'),
        (fiscal_year, 'Fiscal Year'),
        (p_code_instrument, 'Product line/instrument'),
        (f4d_association_value, 'F4D Association Value'),
        (region, 'Region'),
        (country, 'Country'),
        (pillars, 'Pillars')
    ]

    missing_fields = [name for value, name in mandatory_fields if not value]

    # Save values
    save_values = {
            "p_code_instrument": p_code_instrument,
            "country": country,
            "p_code_description": p_code_description,
            "f4d_association": f4d_association,
            "region_id": region_id,
            "pillars": pillars or [],
            "ccts": ccts or [],
            "pillar_explanations": pillar_explanations or {},
            "cct_explanations": cct_explanations or {}
    }

    # Save button
    if st.button("Save", type="primary"):
        # Check for existing entry
        existing_trustfund_fy = session.query(GrantInfo).filter_by(
            trustfund_id=trustfund_id,
            fiscal_year_id=fiscal_year_id,
            deleted=False
        ).first()

        if existing_trustfund_fy and not existing_grant_info:
            st.warning("A Grant Information entry with this Trust Fund and Fiscal Year already exists.")
        else:
            if not missing_fields:
                if existing_grant_info:
                    # Update existing records
                    for field, value in save_values.items():
                        if isinstance(value, list):
                            value = ', '.join(value)
                        if field == 'f4d_association' and isinstance(value, F4DAssociationEnum):
                            value = value.value
                        if isinstance(value, dict):
                            value = str(value)

                        session.query(GrantInfo).filter_by(
                            trustfund_id=existing_grant_info.trustfund_id,
                            fiscal_year_id=fiscal_year_id,
                            field=field
                        ).update({"value": value})

                    session.commit()
                    st.session_state.grant_info_initial_values = current_values
                    st.session_state.grant_info_unsaved_changes = False
                    st.session_state.current_trustfund_id = trustfund_id
                    st.session_state.current_fiscal_year_id = fiscal_year_id
                    st.success("Grant information updated successfully!")
                else:
                    # Create a new GrantInfo instance
                    for field, value in save_values.items():
                        if isinstance(value, list):
                            value = ', '.join(value)
                        if field == 'f4d_association' and isinstance(value, F4DAssociationEnum):
                            value = value.value
                        if isinstance(value, dict):
                            value = str(value)

                        new_grant_info_entry = GrantInfo(
                            trustfund_id=trustfund_id,
                            fiscal_year_id=fiscal_year_id,
                            field=field,
                            value=value,
                            team_id=current_team_id(),
                            deleted=False,
                            created_at=datetime.datetime.now(),
                            updated_at=datetime.datetime.now()
                        )
                        session.add(new_grant_info_entry)

                    session.commit()
                    st.session_state.grant_info_initial_values = current_values
                    st.session_state.grant_info_unsaved_changes = False
                    st.session_state.current_trustfund_id = trustfund_id
                    st.session_state.current_fiscal_year_id = fiscal_year_id
                    st.success("Grant information saved successfully!")
            else:
                st.error(f"Please fill in all mandatory fields: {', '.join(missing_fields)}")

    # Display notification if there are unsaved changes
    if st.session_state.grant_info_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    session.close()


def strategic_objective_progress():
    st.success("### 2. Strategic Objective & Progress")

    # Create a new session
    session = create_session()

    existing_grant_info = session.query(GrantInfo).filter_by(
    trustfund_id=st.session_state.current_trustfund_id, fiscal_year_id=st.session_state.current_fiscal_year_id).first()

    # Initialize variables for text areas
    challenges = strategic_objective = overall_progress = ""
    implementation_challenges = public_communication_external = public_communication_internal = ""

    # If existing data is found, populate the variables with that data
    if existing_grant_info:
        # Retrieve all fields and their corresponding values for the existing grant info
        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=st.session_state.current_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            deleted=False
        ).all()

        # If there is existing data, populate the variables with that data
        for entry in long_format_entries:
            if entry.field == "challenges":
                challenges = entry.value
            elif entry.field == "strategic_objective":
                strategic_objective = entry.value
            elif entry.field == "overall_progress":
                overall_progress = entry.value
            elif entry.field == "implementation_challenges":
                implementation_challenges = entry.value
            elif entry.field == "public_communication_external":
                public_communication_external = entry.value
            elif entry.field == "public_communication_internal":
                public_communication_internal = entry.value

    # Store initial values in session state for change detection
    if "strategic_objective_initial_values" not in st.session_state:
        st.session_state.strategic_objective_initial_values = {
            "challenges": challenges if challenges else "",
            "strategic_objective": strategic_objective if strategic_objective else "",
            "overall_progress": overall_progress if overall_progress else "",
            "implementation_challenges": implementation_challenges if implementation_challenges else "",
            "public_communication_external": public_communication_external if public_communication_external else "",
            "public_communication_internal": public_communication_internal if public_communication_internal else ""
        }
        st.session_state.strategic_objective_unsaved_changes = False
    else:
        # If initial values already exist, update them with the current values
        st.session_state.strategic_objective_initial_values = {
            "challenges": challenges if challenges else "",
            "strategic_objective": strategic_objective if strategic_objective else "",
            "overall_progress": overall_progress if overall_progress else "",
            "implementation_challenges": implementation_challenges if implementation_challenges else "",
            "public_communication_external": public_communication_external if public_communication_external else "",
            "public_communication_internal": public_communication_internal if public_communication_internal else ""
        }
    # Display text areas with existing data if available
    challenges = st.text_area(
        "Challenges the grant is going to address *",
        value=challenges,
        placeholder="What is the key challenge(s) the client country faces that this grant intends to address?"
    )
    strategic_objective = st.text_area(
        "Grant's strategic objective (Max 200 words) *",
        value=strategic_objective,
        placeholder="What the grant is expected to achieve to address the challenges. Max. 200 words."
    )
    overall_progress = st.text_area(
        "Overall progress since inception *",
        value=overall_progress,
        placeholder="Please provide a short summary of the overall progress since inception of the grant towards achieving the strategic objective, with a focus on progress towards outcomes instead of listing deliverables. Include details including developments in client support/interest, coordination and partnerships with other donors, development partners and/or other WB units and IFC; include any relevant lessons learned."
    )
    implementation_challenges = st.text_area(
        "Implementation Challenges",
        value=implementation_challenges,
        placeholder="Please provide any challenges faced so far, any external or unexpected events that affect the implementation or results."
    )
    public_communication_external = st.text_area(
        "Public communication (external)",
        value=public_communication_external,
        placeholder="List external public communications that took place. Examples include a link to a press release, an external conference, counterpart quotes, newspaper, journals, articles, blogs, website, data infographics, brochures, booklet, reports, TV, YouTube video, photos, etc. Send attachments to financefordevelopment@worldbank.org if there is no link."
    )
    public_communication_internal = st.text_area(
        "Public communication (internal)",
        value=public_communication_internal,
        placeholder="List any World Bank intranet appearances (such as links to blog posts, feature stories, Up Front story, photos of internal events, data infographics, etc.). Send attachments to financefordevelopment@worldbank.org if there is no link."
    )

    # Check for changes in form values
    current_values = {
        "challenges": challenges or "",
        "strategic_objective": strategic_objective or "",
        "overall_progress": overall_progress or "",
        "implementation_challenges": implementation_challenges or "",
        "public_communication_external": public_communication_external or "",
        "public_communication_internal": public_communication_internal or ""
    }

    # Detect changes by comparing current values with initial values
    changes_detected = False
    for key, value in current_values.items():
        if normalize(value) != normalize(st.session_state.strategic_objective_initial_values.get(key, "")):
            changes_detected = True
            break
    
    # Update unsaved changes flag
    st.session_state.strategic_objective_unsaved_changes = changes_detected
    
    # Define mandatory fields and their corresponding names
    mandatory_fields = [
        (challenges, 'Challenges the grant is going to address'),
        (strategic_objective, "Grant's strategic objective"),
        (overall_progress, 'Overall progress since inception'),
    ]

    # Check for unfilled mandatory fields
    missing_fields = [name for value, name in mandatory_fields if not value]

    # Add new values in long format
    save_values = [
        ("challenges", challenges),
        ("strategic_objective", strategic_objective),
        ("overall_progress", overall_progress),
        ("implementation_challenges", implementation_challenges),
        ("public_communication_external", public_communication_external),
        ("public_communication_internal", public_communication_internal)
    ]

    if st.button("Save", type="primary"):
        # Update existing record with new values
        if existing_grant_info:
            if not missing_fields:
                # Clear existing entries for the current trustfund and fiscal year, matching fields
                for field in ["challenges", "strategic_objective", "overall_progress", 
                            "implementation_challenges", "public_communication_external", 
                            "public_communication_internal"]:
                    session.query(GrantInfo).filter_by(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=field
                    ).delete()

                for field, value in save_values:
                    new_entry = GrantInfo(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=field,
                        value=value,
                        team_id=current_team_id(),
                        deleted=False,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_entry)

                # Commit the changes to the database
                session.commit()

                # Reset the initial values to the current values after saving
                st.session_state.strategic_objective_initial_values = dict(current_values)
                st.session_state.strategic_objective_unsaved_changes = False
                st.success("Strategic objective progress saved successfully!")
            else:
                st.error(
                    f"Please fill in all mandatory fields: {', '.join(missing_fields)}")
        else:
            st.warning(
                "No Grant Info exists! Please create one in Basic Grant Information subpage")
            
    # Close the session
    session.close()

    # Display notification if there are unsaved changes
    if st.session_state.strategic_objective_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")


def lending_operations():
    st.success("### 3. Operations Informed and Country Engagements Informed by F4D")

    operations()
    cpfs()


def operations():
    # Create a new session
    session = create_session()

    existing_grant_info = session.query(GrantInfo).filter_by(
    trustfund_id=st.session_state.current_trustfund_id, fiscal_year_id=st.session_state.current_fiscal_year_id).first()

    # Initialize the list in session state if it doesn't exist
    if 'operation_list' not in st.session_state:
        st.session_state['operation_list'] = []


    # Populate the session state with existing operations only if the session is empty
    if not st.session_state['operation_list']:
        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=st.session_state.current_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            deleted=False
        ).all()
    

        for entry in long_format_entries:
            if entry.field.startswith("operation_"):
                operation_data = eval(entry.value)  # Assuming the value is stored in a dict format
                st.session_state['operation_list'].append(operation_data)
            else:
                st.session_state['operation_list'] =[]
                st.session_state.operations_unsaved_changes = False
                st.session_state.operations_initial_values = []

    # Variable to hold index of operation to delete
    operation_to_delete = None
    

    # Display the input fields for each operation
    for i, operation in enumerate(st.session_state['operation_list']):
        operation = st.session_state['operation_list'][i]
        st.subheader(f"Operation {i + 1}")
            
        # Define a function to mark changes
        def mark_operation_changed():
            st.session_state.operations_unsaved_changes = True

        operation['informed_operation'] = st.radio(
            "Did the grant inform a Board approved World Bank lending operation?", [
                "Yes", "No"],
            index=0 if operation['informed_operation'] == "Yes" else (
        1 if operation['informed_operation'] == "No" else None),
            key=f"informed_operation_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed)

        st.markdown(
            "F4D will ask the Regional PM to clear the information you will provide below. Please ensure you provide accurate information below."
        )

        # Text input with on_change handler
        operation['p_number'] = st.text_input(
            "P number of the informed operation",
            value=operation['p_number'],
            key=f"p_number_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed)

        # Define the options for the selectbox
        options = ["IPF", "PforR", "DPF", "Other"]

        # Default to None if operation['p_code_instrument'] is not in options
        selected_index = None if operation['p_code_instrument'] not in options else options.index(operation['p_code_instrument'])

        # Set the selected instrument using selectbox with on_change handler
        operation['p_code_instrument'] = st.selectbox(
            "P code instrument of the informed operation",
            options,
            index=selected_index,
            key=f"p_code_instrument_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed
        )

        # Check if "Other" is selected
        if operation['p_code_instrument'] == "Other":
            operation['p_code_instrument_description'] = st.text_input(
                "If other, please describe:",
                value=operation['p_code_instrument_description'],
                key=f"p_code_instrument_description_{existing_grant_info.id}_{i}",
                on_change=mark_operation_changed
            )
        else:
            operation['p_code_instrument_description'] = None

        operation['approval_fy'] = st.text_input(
            "Approval FY of the informed lending operation",
            value=operation['approval_fy'],
            key=f"approval_fy_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed
        )

        operation['operation_name'] = st.text_input(
            "Operation name",
            value=operation['operation_name'],
            key=f"operation_name_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed
        )

        operation['total_commitment'] = st.number_input(
            "Total commitment amount of the informed operation (in US$ millions)",
            value=float(operation['total_commitment']) if operation['total_commitment'] else 0.00,
            key=f"total_commitment_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed, format="%f"
        )

        operation['informed_by_f4d'] = st.number_input(
            "How much out of the total amount was informed by the F4D grant? (e.g., for the relevant component(s) - in US$ millions)",
            value=float(operation['informed_by_f4d']) if operation['informed_by_f4d'] else 0.00,
            key=f"informed_by_f4d_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed, format="%f"
        )

        operation['evidence'] = st.text_area(
            "EVIDENCE: How did the grant contribute to the lending operation's objective?",
            placeholder="Describe how the F4D grant informed the operation. Clearly articulate the relevant sections and references to F4D support in a way the information can be verified (e.g., copy-pasting the relevant sections).",
            value=operation['evidence'],
            key=f"evidence_{existing_grant_info.id}_{i}",
            on_change=mark_operation_changed
        )

        col1, col2 = st.columns([2, 2])

        with col1:
            # Show the Save button for each operation
            if st.button(f"Save Operation {i + 1}", key=f"save_operation_{existing_grant_info.id}_{i}"):
                if st.session_state.current_trustfund_id and st.session_state.current_fiscal_year_id:
                    # Prepare to save each operation in long format
                    # Clear existing entries for the current trustfund and fiscal year, matching fields
                    session.query(GrantInfo).filter_by(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=f"operation_{i + 1}"  # Unique field for each operation
                    ).delete()

                    # Save the operation in long format
                    new_entry = GrantInfo(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=f"operation_{i + 1}",  # Unique field name
                        value=str({
                            "informed_operation": operation['informed_operation'],
                            "p_number": operation['p_number'],
                            "p_code_instrument": operation['p_code_instrument'],
                            "p_code_instrument_description": operation['p_code_instrument_description'],
                            "approval_fy": operation['approval_fy'],
                            "operation_name": operation['operation_name'],
                            "total_commitment": operation['total_commitment'],
                            "informed_by_f4d": operation['informed_by_f4d'],
                            "evidence": operation['evidence']
                        }),
                        team_id=current_team_id(),
                        deleted=False,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_entry)
                    session.commit()

                    # Reset the initial values to the current values after saving
                    st.session_state.operations_initial_values = deep_copy_operations(st.session_state['operation_list'])
                    st.session_state.operations_unsaved_changes = False

                    st.success(f"Operation {i + 1} saved successfully!")

        with col2:
            # Show the Delete button for each operation
            if st.button(f"Delete Operation {i + 1}", key=f"delete_operation_{existing_grant_info.id}_{i}"):
                operation_to_delete = i  # Set the index of the operation to delete
                # Mark changes as unsaved when deleting an operation
                st.session_state.operations_unsaved_changes = True

    # Button to add a new operation
    if st.button("Add Operation", key=f"add_operation", type="primary"):
        if existing_grant_info:
            st.session_state['operation_list'].append({
                "informed_operation": "",
                "p_number": "",
                "p_code_instrument": "",
                "p_code_instrument_description": "",
                "approval_fy": "",
                "operation_name": "",
                "total_commitment": "",
                "informed_by_f4d": "",
                "evidence": ""
            })
            # Mark changes as unsaved when adding a new operation
            st.session_state.operations_unsaved_changes = True
            st.rerun()  # Rerun to display the new operation input fields
        else:
            st.warning(
                "No Grant Info exists! Please create one in Basic Grant Information subpage")


    # Handle deletion outside the loop to avoid index shift issues
    if operation_to_delete is not None:
       # Remove the operation from the list
        st.session_state['operation_list'].pop(operation_to_delete)

        # Delete the corresponding entry from the database
        session.query(GrantInfo).filter_by(
            trustfund_id=st.session_state.current_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            field=f"operation_{operation_to_delete + 1}"  # Unique field for the operation being deleted
        ).delete()

        session.commit()

        # Reset the initial values to the current values after saving
        st.session_state.operations_initial_values = deep_copy_operations(st.session_state['operation_list'])
        st.session_state.operations_unsaved_changes = False

        st.success(
            f"Operation {operation_to_delete + 1} deleted successfully!")
        st.rerun()

    # Check for changes by comparing current operations list with initial values
    if "operations_initial_values" in st.session_state:
        current_operations = st.session_state['operation_list']
        initial_operations = st.session_state.operations_initial_values
        
        # Only check if the lengths are the same (if they're different, we already know there's a change)
        if len(current_operations) == len(initial_operations):
            changes_detected = False
            for i, (current_op, initial_op) in enumerate(zip(current_operations, initial_operations)):
                for key in current_op:
                    # Normalize None values to empty strings for comparison
                    current_value = "" if current_op.get(key) is None else str(current_op.get(key, ""))
                    initial_value = "" if initial_op.get(key) is None else str(initial_op.get(key, ""))
                    
                    if current_value != initial_value:
                        changes_detected = True
                        break
                if changes_detected:
                    break
            
            # Only update the flag if we're setting it to True (to avoid overriding manual flag settings)
            if changes_detected:
                st.session_state.operations_unsaved_changes = True
        else:
            st.session_state.operations_unsaved_changes = True

    # Add a message about navigation risks if there are unsaved changes
    if st.session_state.get('operations_unsaved_changes', False):
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    # Close the session
    session.close()


# Helper function to make a deep copy of operations list
def deep_copy_operations(operations_list):
    if not operations_list:
        return []
    
    return [
        {
            # Convert None values to empty strings for consistent comparison
            "informed_operation": "" if op.get("informed_operation") is None else op.get("informed_operation", ""),
            "p_number": "" if op.get("p_number") is None else op.get("p_number", ""),
            "p_code_instrument": "" if op.get("p_code_instrument") is None else op.get("p_code_instrument", ""),
            "p_code_instrument_description": "" if op.get("p_code_instrument_description") is None else op.get("p_code_instrument_description", ""),
            "approval_fy": "" if op.get("approval_fy") is None else op.get("approval_fy", ""),
            "operation_name": "" if op.get("operation_name") is None else op.get("operation_name", ""),
            "total_commitment": "" if op.get("total_commitment") is None else op.get("total_commitment", ""),
            "informed_by_f4d": "" if op.get("informed_by_f4d") is None else op.get("informed_by_f4d", ""),
            "evidence": "" if op.get("evidence") is None else op.get("evidence", "")
        }
        for op in operations_list
    ]


def cpfs():
    # Create a new session
    session = create_session()

    data = read_data()

    existing_grant_info = session.query(GrantInfo).filter_by(
        trustfund_id=st.session_state.current_trustfund_id, fiscal_year_id=st.session_state.current_fiscal_year_id).first()

    # Initialize the list in session state if it doesn't exist
    if 'cpf_list' not in st.session_state:
        st.session_state['cpf_list'] = []

    # Populate the session state with existing cpfs only if the session is empty
    if not st.session_state['cpf_list']:
        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=st.session_state.current_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            deleted=False
        ).all()

        for entry in long_format_entries:
            if entry.field.startswith("cpf_"):
                # Assuming the value is stored as a stringified dictionary
                cpf_data = eval(entry.value)  # Use caution with eval
                st.session_state['cpf_list'].append(cpf_data)
            else:
                st.session_state['cpf_list'] = []
                st.session_state.cpfs_unsaved_changes = False  # Reset unsaved changes flag
                st.session_state.cpfs_initial_values = []  # Reset initial values
            


            # Store initial values for change detection
            if "cpfs_initial_values" not in st.session_state:
                st.session_state.cpfs_initial_values = deep_copy_cpfs(st.session_state['cpf_list'])
                st.session_state.cpfs_unsaved_changes = False


    cpf_to_delete = None  # Variable to hold index of cpf to delete

    # Display the input fields for each cpf
    for i in range(len(st.session_state['cpf_list'])):
        cpf = st.session_state['cpf_list'][i]
        st.subheader(f"CPF {i + 1}")

        # Define a function to mark changes
        def mark_cpf_changed():
            st.session_state.cpfs_unsaved_changes = True

        cpf['informed_cpf'] = st.radio(
            "Did the grant inform a CPF?", [
                "Yes", "No"],
            index=0 if cpf['informed_cpf'] == "Yes" else (
        1 if cpf['informed_cpf'] == "No" else None),
            key=f"informed_cpf_{i}",
            on_change=mark_cpf_changed
)

        st.markdown(
            "F4D will ask the Regional PM to clear the information you will provide below. Please ensure you provide accurate information below."
        )


        # Ensure cpf['country'] is a list
        if isinstance(cpf['country'], str):
            default_countries = cpf['country'].split(', ') if cpf['country'] else []
        else:
            default_countries = cpf['country'] if isinstance(cpf['country'], list) else []


        # Sort the countries by name
        sorted_countries = sorted([c[0] for c in data["countries"]])

        # Select countries with pre-selection if existing data is present
        cpf['country'] = st.multiselect(
            "Country (multiple choice):", 
            sorted_countries,
            default=default_countries,
            key=f"cpf_country_{i}",
            on_change=mark_cpf_changed
        )

        # Read the fiscal year from the selectbox
        cpf['year'] = st.selectbox(
            "Fiscal Year:",
            ["Select a fiscal year"] + [option[0] for option in data["fiscal_years"]],
            index=None if not cpf['year'] else next(
                (i for i, option in enumerate(data["fiscal_years"], 1) if option[0] == cpf['year']),
                0
            ), key=f"cpf_year_{i}",
            on_change=mark_cpf_changed
        )

        # Extract fiscal_year_id based on the selection
        fiscal_year_id = None
        for fy in data["fiscal_years"]:
            if fy[0] == cpf['year'] :
                fiscal_year_id = fy[1]
                break

        cpf['evidence'] = st.text_area(
            "EVIDENCE: How did the grant contribute to the CPF?",
            placeholder="Describe how the F4D grant informed the CPF.",
            value=cpf['evidence'], key=f"cpf_evidence_{i}",
            on_change=mark_cpf_changed
        )

        col1, col2 = st.columns([2, 2])

        with col1:
            # Show the Save button for each cpf
            if st.button(f"Save CPF {i + 1}", key=f"save_cpf_{fiscal_year_id}_{i}"):
                if st.session_state.current_trustfund_id and st.session_state.current_fiscal_year_id:
                    # Clear existing entries for the current trustfund and fiscal year, matching fields
                    session.query(GrantInfo).filter_by(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=f"cpf_{i + 1}"  # Unique field for each CPF
                    ).delete()

                    # Save the CPF in long format
                    new_entry = GrantInfo(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=f"cpf_{i + 1}",  # Unique field name
                        value=str({
                            "informed_cpf": cpf['informed_cpf'],
                            "country": cpf['country'],
                            "year": cpf['year'],
                            "evidence": cpf['evidence']
                        }),
                        team_id=current_team_id(),
                        deleted=False,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_entry)
                    session.commit()

                    st.session_state.cpfs_unsaved_changes = False  # Mark as saved
                    # Reset the initial values to the current values after saving
                    st.session_state.cpfs_initial_values = deep_copy_cpfs(st.session_state['cpf_list'])

                    st.success(f"CPF {i + 1} saved successfully!")

        with col2:
            # Show the Delete button for each cpf
            if st.button(f"Delete CPF {i + 1}", key=f"delete_cpf_{fiscal_year_id}_{i}"):
                cpf_to_delete = i  # Set the index of the cpf to delete
                st.session_state.cpfs_unsaved_changes = True  # Mark as unsaved


    # Button to add a new deliverable entry
    if st.button("Add CPF", key=f"add_cpf", type="primary"):
        if existing_grant_info:
            st.session_state['cpf_list'].append({
                "informed_cpf": "",
                "country": "",
                "year": "",
                "evidence": ""
            })
            st.session_state.cpfs_unsaved_changes = True  # Mark as unsaved
            st.rerun()  # Rerun to display the new CPF input fields
        else:
            st.warning(
                "No Grant Info exists! Please create one in Basic Grant Information subpage")


    # Handle deletion outside the loop to avoid index shift issues
    if cpf_to_delete is not None:
        # Remove the cpf from the list
        st.session_state['cpf_list'].pop(cpf_to_delete)

        # Update database after deletion
        session.query(GrantInfo).filter_by(
            trustfund_id=st.session_state.current_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            field=f"cpf_{cpf_to_delete + 1}"  # Unique field for the CPF being deleted
        ).delete()
        
        # Commit the changes to the database
        session.commit()

        # Reset the initial values to the current values after saving
        st.session_state.cpfs_initial_values = deep_copy_cpfs(st.session_state['cpf_list'])
        st.session_state.cpfs_unsaved_changes = False

        st.success(
            f"CPF {cpf_to_delete + 1} deleted successfully!")
        st.rerun()

    # Check for changes by comparing current cpfs list with initial values
    if "cpfs_initial_values" in st.session_state:
        current_cpfs = st.session_state['cpf_list']
        initial_cpfs = st.session_state.cpfs_initial_values

        # Only check if the lengths are the same
        if len(current_cpfs) == len(initial_cpfs):
            changes_detected = False
            for i, (current_cpf, initial_cpf) in enumerate(zip(current_cpfs, initial_cpfs)):
                for key in current_cpf:
                    # Normalize None values to empty strings for comparison
                    current_value = "" if current_cpf.get(key) is None else str(current_cpf.get(key, ""))
                    initial_value = "" if initial_cpf.get(key) is None else str(initial_cpf.get(key, ""))

                    if current_value != initial_value:
                        changes_detected = True
                        break
                if changes_detected:
                    break
            
            # Update the flag if changes are detected
            if changes_detected:
                st.session_state.cpfs_unsaved_changes = True
        else:
            st.session_state.cpfs_unsaved_changes = True

    # Add a message about navigation risks if there are unsaved changes
    if st.session_state.get('cpfs_unsaved_changes', False):
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")


    # Close the session
    session.close()


# Helper function to make a deep copy of operations list
def deep_copy_cpfs(cpfs_list):
    if not cpfs_list:
        return []
    
    return [
        {
            # Convert None values to empty strings for consistent comparison
            "informed_cpf": "" if cp.get("informed_cpf") is None else cp.get("informed_cpf", ""),
            "country": "" if cp.get("country") is None else cp.get("country", ""),
            "year": "" if cp.get("year") is None else cp.get("year", ""),
            "evidence": "" if cp.get("evidence") is None else cp.get("evidence", "")
        }
        for cp in cpfs_list
    ]


def collaboration_partnership():
    st.success("### 4. Collaboration/Partnership")

    # Create a new session
    session = create_session()

    # Fetch the existing GrantInfo instance based on the current trustfund_id
    existing_grant_info = session.query(GrantInfo).filter_by(
        trustfund_id=st.session_state.current_trustfund_id, fiscal_year_id=st.session_state.current_fiscal_year_id).first()

    # Initialize variables for the form fields
    collaborations = []
    other_teams = ""
    other_ifis = ""
    other_orgs = ""
    describe_collaboration = ""
    lessons_learned = ""

    # If there is existing data, populate the variables with that data
    if existing_grant_info:
        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=st.session_state.current_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            deleted=False
        ).all()

        for entry in long_format_entries:
            if entry.field == "collaborations":
                collaborations = eval(entry.value)  
            elif entry.field == "other_teams":
                other_teams = entry.value
            elif entry.field == "other_ifis":
                other_ifis = entry.value
            elif entry.field == "other_orgs":
                other_orgs = entry.value
            elif entry.field == "describe_collaboration":
                describe_collaboration = entry.value
            elif entry.field == "lessons_learned":
                lessons_learned = entry.value

    # Store initial values in session state for change detection
    if "collaboration_initial_values" not in st.session_state:
        st.session_state.collaboration_initial_values = {
            "collaborations": collaborations if collaborations else [],
            "other_teams": other_teams if other_teams else "",
            "other_ifis": other_ifis if other_ifis else "",
            "other_orgs": other_orgs if other_orgs else "",
            "describe_collaboration": describe_collaboration if describe_collaboration else "",
            "lessons_learned": lessons_learned if lessons_learned else ""
        }
        st.session_state.collaboration_unsaved_changes = False
    else:
        # If initial values already exist, use them
        st.session_state.collaboration_initial_values = {
            "collaborations": collaborations if collaborations else [],
            "other_teams": other_teams if other_teams else "",
            "other_ifis": other_ifis if other_ifis else "",
            "other_orgs": other_orgs if other_orgs else "",
            "describe_collaboration": describe_collaboration if describe_collaboration else "",
            "lessons_learned": lessons_learned if lessons_learned else ""
        }

    default_collaborations = collaborations if collaborations else []

    # Multi-select for collaboration options with default values
    new_collaborations = st.multiselect(
        "Is the grant delivered in collaboration/partnership with other World Bank teams (e.g. other GPs), IFC, IMF, or other MDBs/IFIs/bilateral organizations? *", [
            "Other World Bank teams (e.g. GPs)",
            "IFC",
            "IMF",
            "Other IFIs/MDBs/bilateral organizations",
            "Other organizations (e.g. CSOs, private sector, academia, think tanks)",
            "No"
        ], default=default_collaborations, key="collaborations_input")

    # If "Yes" options are selected, ask for additional details
    new_other_teams = ""
    new_other_ifis = ""
    new_other_orgs = ""
    new_describe_collaboration = ""
    new_lessons_learned = ""
    
    if new_collaborations:
        if "Other World Bank teams (e.g. GPs)" in new_collaborations:
            new_other_teams = st.text_input(
                "Which teams?", value=other_teams, key="other_teams_input")

        if "Other IFIs/MDBs/bilateral organizations" in new_collaborations:
            new_other_ifis = st.text_input(
                "Which organizations?", value=other_ifis, key="other_ifis_input")

        if "Other organizations (e.g. CSOs, private sector, academia, think tanks)" in new_collaborations:
            new_other_orgs = st.text_input(
                "Which other organizations?", value=other_orgs, key="other_orgs_input")
        
        if "No" not in new_collaborations:
            new_describe_collaboration = st.text_area(
                "Describe the collaboration",
                placeholder="In which areas of the grant is the collaboration taking place/took place? What strengths or value-added by the partners were leveraged in the collaboration/partnership? What role did the World Bank play in the collaboration/partnership?",
                value=describe_collaboration,
                key="describe_collaboration_input"
            )

            new_lessons_learned = st.text_area(
                "Lessons learned",
                placeholder="Please describe any lessons learned from the collaboration. How is the partnership expected to evolve?",
                value=lessons_learned,
                key="lessons_learned_input"
            )

    # Check for changes in form values
    current_values = {
        "collaborations": new_collaborations or [],
        "other_teams": new_other_teams or "",
        "other_ifis": new_other_ifis or "",
        "other_orgs": new_other_orgs or "",
        "describe_collaboration": new_describe_collaboration or "",
        "lessons_learned": new_lessons_learned or ""
    }
    
    # Detect changes by comparing current values with initial values
    changes_detected = False

    for key, value in current_values.items():
        if key == "collaborations":
            # Special handling for list comparison
            initial_list = st.session_state.collaboration_initial_values.get(key, [])
            if sorted(value) != sorted(initial_list):
                changes_detected = True
                break
        elif value != st.session_state.collaboration_initial_values.get(key, ""):
            changes_detected = True
            break
        
    # Update unsaved changes flag
    st.session_state.collaboration_unsaved_changes = changes_detected

    # Define mandatory fields and their corresponding names
    mandatory_fields = [
        (new_collaborations, 'Is the grant delivered in collaboration/partnership with other World Bank teams (e.g. other GPs), IFC, IMF, or other MDBs/IFIs/bilateral organizations?')
    ]

    # Check for unfilled mandatory fields
    missing_fields = [name for value, name in mandatory_fields if not value]

    # Save button to handle saving the data
    if st.button("Save", type="primary"):
        if existing_grant_info:
            if not missing_fields:
                # Update existing record with new values
                # Clear existing entries for the current trustfund and fiscal year, matching fields
                for field in ["collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned"]:
                    session.query(GrantInfo).filter_by(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=field
                    ).delete()

                # Save new values in long format
                for key, value in current_values.items():
                    if isinstance(value, list):
                        value = str(value)
                    new_entry = GrantInfo(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field=key,
                        value=value,
                        team_id=current_team_id(),
                        deleted=False,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_entry)

                # Commit the changes to the database
                session.commit()
                
                # Reset the initial values to the current values after saving
                st.session_state.collaboration_initial_values = dict(current_values)
                st.session_state.collaboration_unsaved_changes = False
                
                st.success("Collaboration information saved successfully!")
            else:
                st.error(
                    f"Please fill in all mandatory fields: {', '.join(missing_fields)}")
        else:
            st.warning(
                "No Grant Info exists! Please create one in Basic Grant Information subpage")

    # Display notification if there are unsaved changes
    if st.session_state.collaboration_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    # Close the session
    session.close()


def show_previous_fiscal_year_deliverables(trustfund_id, deliverable_id, fiscal_year_id):
    # Create a session
    session = create_session()

    # Fetch the last existing fiscal year data from grant_info table
    last_fiscal_year_info = (
        session.query(GrantInfo)
        .filter(
            GrantInfo.trustfund_id == trustfund_id, 
            GrantInfo.field == "deliverables", 
            GrantInfo.fiscal_year_id != fiscal_year_id
        )
        .order_by(GrantInfo.fiscal_year_id.desc())
        .first()
    )

    if not last_fiscal_year_info:
        session.close()
        return
    
    # Parse the JSON data from the deliverable entry
    try:
        # Assuming the value is stored as a JSON string
        all_deliverable_data = eval(last_fiscal_year_info.value)
    except:
        st.write("Error parsing deliverable data from previous fiscal year.")
        session.close()
        return
    
    # Extract the specific deliverable data
    specific_deliverable = all_deliverable_data.get(str(deliverable_id), {})
    
    if not specific_deliverable:
        # This specific deliverable doesn't exist in the previous fiscal year
        session.close()
        return
    
    # Extract the relevant information for display
    progress_update = specific_deliverable.get('input_value', '')
    progress_status = specific_deliverable.get('progress', '')
    
    # Create a list for display
    deliverable_display = [{
        "Fiscal Year": last_fiscal_year_info.fiscal_year,
        "Progress Update": progress_update,
        "Progress": progress_status
    }]
    
    # Convert the list of dictionaries to a DataFrame
    deliverable_df = pd.DataFrame(deliverable_display)

    # Convert any columns to standard types, if necessary
    deliverable_df['Fiscal Year'] = deliverable_df['Fiscal Year'].astype(str)

    # Display the data in a table format
    st.write("### Previous Fiscal Year Deliverable")
    #st.table(deliverable_display)
    st.dataframe(deliverable_df, use_container_width=True, hide_index=True)

    # Close the session
    session.close()


def get_previous_fiscal_year_deliverables(trustfund_id, deliverable_id, fiscal_year_id):
    # Create a session
    session = create_session()
    
    # Fetch the last existing fiscal year data from grant_info table (excluding current fiscal year)
    last_fiscal_year_info = (
        session.query(GrantInfo)
        .filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.field == "deliverables",
            GrantInfo.fiscal_year_id != fiscal_year_id
        )
        .order_by(GrantInfo.fiscal_year_id.desc())
        .first()
    )
    
    if not last_fiscal_year_info:
        session.close()
        return None  # No deliverables found for previous fiscal years
    
    # Parse the deliverables data from JSON
    try:
        all_deliverable_data = eval(last_fiscal_year_info.value)
    except:
        session.close()
        return None  # Error parsing data
    
    # Check if the specified deliverable_id exists in the deliverables data
    if str(deliverable_id) in all_deliverable_data:
        session.close()

        return all_deliverable_data[str(deliverable_id)]
    else:
        session.close()
        return None  # No deliverable found for the specified deliverable_id


def deliverables():
    st.success("### 5. Outputs/deliverables")
    
    # Create a session
    session = create_session()
    
    # Fetch existing indicators based on current grant ID
    existing_grant_info = session.query(GrantInfo).filter_by(
        trustfund_id=st.session_state.current_trustfund_id, fiscal_year_id=st.session_state.current_fiscal_year_id, deleted=False).first()

    trustfund = session.query(TrustFund).filter(TrustFund.name == current_username(),
                                              TrustFund.team_id == current_team_id()
                                              ).first()

    if trustfund:
        trustfund_id = trustfund.id
    else:
        st.error(f"No TrustFund found for this user - {current_username()}")
        return

    # Fetch all mapping entries for the current trustfund_id
    mappings = session.query(TrustFundIndicatorMapping).filter(
        TrustFundIndicatorMapping.trustfund_id == trustfund_id).all()

    # Check if there are no mappings
    if not mappings:
        st.write(
            f"No deliverables found for the provided Trust Fund - {trustfund.name}")
        return

    # Initialize a dictionary to hold input values for all deliverables
    deliverables_data = {}

    # Check if there is existing data in the deliverables column and parse it
    if existing_grant_info:
        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=trustfund_id,
            fiscal_year_id=existing_grant_info.fiscal_year_id,
            deleted=False
        ).all()


        for entry in long_format_entries:
            if entry.field.startswith("deliverables"):
                deliverables_data = ast.literal_eval(entry.value)

    # Initialize session state for tracking changes
    if 'deliverables_initial_values' not in st.session_state:
        st.session_state.deliverables_initial_values = {
                    str(mapping.indicator_id): {
                        "input_value": deliverables_data.get(str(mapping.indicator_id), {}).get("input_value", None),
                        "progress": deliverables_data.get(str(mapping.indicator_id), {}).get("progress", ""),
<<<<<<< HEAD
=======
                        "deliverable_quantity": deliverables_data.get(str(mapping.indicator_id), {}).get("deliverable_quantity", ""),
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                        "description": deliverables_data.get(str(mapping.indicator_id), {}).get("description", ""),
                        "data_source": deliverables_data.get(str(mapping.indicator_id), {}).get("data_source", ""),
                        "next_steps": deliverables_data.get(str(mapping.indicator_id), {}).get("next_steps", ""),
                        "supporting_materials_url": deliverables_data.get(str(mapping.indicator_id), {}).get("supporting_materials_url", "")
                    }
                    for mapping in mappings if str(mapping.indicator_id) in deliverables_data.keys()
                }
  
        st.session_state.deliverables_unsaved_changes = False

    # Initialize a list to hold missing mandatory fields
    missing_mandatory_fields = []

    # Iterate through each mapping and display appropriate input fields
    for mapping in mappings:
        indicator = session.query(Indicator).filter(
            Indicator.id == mapping.indicator_id, Indicator.custom_indicator == False).first()

        if indicator:
            mandatory_char = ""
            if mapping.relation_ship == "Mandatory":
                mandatory_char = "*"

            # Pre-fill the input field with existing data if available
            input_value = deliverables_data.get(str(mapping.indicator_id), {}).get("input_value", None)
            progress = deliverables_data.get(str(mapping.indicator_id), {}).get("progress", "")
<<<<<<< HEAD
=======
            deliverable_quantity = deliverables_data.get(str(mapping.indicator_id), {}).get("deliverable_quantity", "")
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
            description = deliverables_data.get(str(mapping.indicator_id), {}).get("description", "")
            data_source = deliverables_data.get(str(mapping.indicator_id), {}).get("data_source", "")
            next_steps = deliverables_data.get(str(mapping.indicator_id), {}).get("next_steps", "")
            supporting_materials_url = deliverables_data.get(str(mapping.indicator_id), {}).get("supporting_materials_url", "")

            # Fetch previous fiscal year deliverables
            previous_deliverables = get_previous_fiscal_year_deliverables(trustfund_id, mapping.indicator_id, st.session_state.current_fiscal_year_id)

            # If previous fiscal year deliverables exist, use them to pre-fill the fields
            if previous_deliverables:
                previous_description = previous_deliverables.get('description', '')
                previous_data_source = previous_deliverables.get('data_source', '')
                previous_input_value = previous_deliverables.get('input_value', None)

                
                # Use previous values only if existing values are empty
                if not description:
                    description = previous_description
                if not data_source:
                    data_source = previous_data_source
                if input_value is None:
                    input_value = previous_input_value

           # Store initial values for change tracking
            st.session_state.deliverables_initial_values[str(mapping.indicator_id)] = {
                "input_value": input_value if input_value else None,
                "progress": progress,
<<<<<<< HEAD
=======
                "deliverable_quantity": deliverable_quantity,
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                "description": description,
                "data_source": data_source,
                "next_steps": next_steps,
                "supporting_materials_url": supporting_materials_url
            }

            with st.expander(indicator.indicator_name):
                if not indicator.indicator_prompt.endswith(('.', ':')):
                    indicator.indicator_prompt += '' #'.'

                show_previous_fiscal_year_deliverables(trustfund_id, str(mapping.indicator_id), st.session_state.current_fiscal_year_id)

                # Display input fields with on_change callback
                if indicator.unit_of_measurement == 'Date':
                    input_value = st.date_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", 
                        value=input_value,  
                        key=f"date_input_{mapping.id}")

                elif indicator.unit_of_measurement == 'Number':
                    input_value = st.number_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", 
                        value=input_value,  
                        key=f"number_input_{mapping.id}")
 
                elif indicator.unit_of_measurement == 'Short Text':
                    input_value = st.text_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", 
                        value=input_value,  
                        key=f"short_text_input_{mapping.id}", 
                        placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                elif indicator.unit_of_measurement == 'Long Text':
                    input_value = st.text_area(
                        f"{indicator.indicator_prompt} {mandatory_char}", 
                        value=input_value,  
                        key=f"long_text_input_{mapping.id}", 
                        placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                elif indicator.unit_of_measurement == 'Percentage':
                    input_value = st.number_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", 
                        value=input_value,  
                        key=f"percentage_input_{mapping.id}",)
                elif indicator.unit_of_measurement == 'Categorical':
                    # Read categories from the categorical_unit column and split by ','
                    if indicator.categorical_unit:
                        categories = [cat.strip()
                                    for cat in indicator.categorical_unit.split(',')]
                    else:
                        categories = []  # Handle the case where categorical_unit is None or empty

                    # Display the select box with dynamically loaded categories
                    input_value = st.selectbox(
<<<<<<< HEAD
                        f"{indicator.indicator_prompt} {mandatory_char}", 
                        categories, 
                        index=categories.index(input_value) if input_value in categories else None, 
=======
                        f"{indicator.indicator_prompt} {mandatory_char}",
                        categories,
                        index=categories.index(input_value) if input_value in categories else None,
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                        key=f"categorical_input_{mapping.id}"
                    )
                else:
                    st.write("No valid unit of measurement provided.")
                    continue

                progress = st.text_input(
                    "Number of deliverable(s) ",
                    placeholder="Count the unique number of deliverable(s) ever achieved since the grant activation.",
                    value=progress,
                    key=f"progress_{mapping.id}",
                )

<<<<<<< HEAD
=======
                deliverable_quantity = st.text_input(
                    "Deliverable quantity",
                    placeholder="Enter the number or quantity of this deliverable (e.g., number of MSMEs informed, number of reports produced).",
                    value=deliverable_quantity,
                    key=f"deliverable_quantity_{mapping.id}",
                )

>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                next_steps = st.text_area(
                    "Next steps and any required adjustments in FY",
                    value=next_steps,
                    placeholder="Describe any adjustments to the deliverable(s) that will be required going forward.",
                    key=f"next_steps_{mapping.id}",
                )

                supporting_materials_url = st.text_input(
                    "URL(link) of any photos, videos, articles, or related items",
                    value=supporting_materials_url,
                    key=f"supporting_materials_url_{mapping.id}",
                )

                description = st.text_area(
                    "Brief description of the deliverable(s), including risk of delay",
                    placeholder="Add detailed information to help the donors understand the details of the deliverable(s), including risk of delay.",
                    value=description,
                    key=f"description_{mapping.id}"
                )

                data_source = st.text_input(
                    "Data source",
                    placeholder="Provide link to the extent possible",
                    value=data_source,
                    key=f"data_source_{mapping.id}",
                )

            # Check if the indicator_id already exists in deliverables_data
            if mapping.indicator_id in deliverables_data:
                # Update existing entry
                deliverables_data[str(mapping.indicator_id)].update({
                    "input_value": input_value,
                    "progress": progress,
<<<<<<< HEAD
=======
                    "deliverable_quantity": deliverable_quantity,
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                    "description": description,
                    "data_source": data_source,
                    "next_steps": next_steps,
                    "supporting_materials_url": supporting_materials_url
                })
            else:
                # Add new entry
                deliverables_data[str(mapping.indicator_id)] = {
                    "input_value": input_value,
                    "progress": progress,
<<<<<<< HEAD
=======
                    "deliverable_quantity": deliverable_quantity,
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                    "description": description,
                    "data_source": data_source,
                    "next_steps": next_steps,
                    "supporting_materials_url": supporting_materials_url
                }



            # Check if the field is mandatory and ensure it has a value
            if mapping.relation_ship == "Mandatory" and (input_value is None or input_value == "" or (isinstance(input_value, (int, float)) and input_value < 0)):
                missing_mandatory_fields.append(indicator.indicator_prompt)
            # Uncomment to make this field "Number of deliverable(s)" mandatory
            #if progress is None or progress == "":
            #    missing_mandatory_fields.append("Number of deliverable(s)")  # Progress is mandatory
    

    # Check for changes in form values
    current_values = deliverables_data

    # Detect changes by comparing current values with initial values
    changes_detected = False

    for key, value in current_values.items():
        if value != st.session_state.deliverables_initial_values.get(str(key), {}):
            changes_detected = True
            break
    
    # Update unsaved changes flag
    st.session_state.deliverables_unsaved_changes = changes_detected

    if st.button("Save", key=f"save_deliverable", type="primary"):
        if deliverables_data:
            if existing_grant_info:
                if missing_mandatory_fields == []:  # Check if there are missing mandatory fields
                    # Clear existing entries for the current trustfund and fiscal year, matching deliverable fields
                    session.query(GrantInfo).filter(
                        GrantInfo.trustfund_id == existing_grant_info.trustfund_id,
                        GrantInfo.fiscal_year_id == existing_grant_info.fiscal_year_id,
                        GrantInfo.field == "deliverables"
                    ).delete(synchronize_session=False)
                    
                    # Save new values in long format using keys as they are
                    new_entry = GrantInfo(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field="deliverables",
                        value=str(deliverables_data),
                        team_id=current_team_id(),
                        deleted=False,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_entry)


                    session.commit()
                    st.success("Outputs/deliverables saved successfully!")
                    
                    # Reset change tracking after save
                    st.session_state.deliverables_unsaved_changes = False
                    st.session_state.deliverables_initial_values = current_values
                else:
                    st.error("Please fill in all mandatory fields: " +
                            ", ".join(missing_mandatory_fields))
            else:
                st.warning(
                    "No Grant Info exists! Please create one in Basic Grant Information subpage")
        else:
            st.error("No deliverables were captured.")

        
    # Display a warning if there are unsaved changes
    if st.session_state.deliverables_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    session.close()
            

def show_previous_fiscal_year_indicators(trustfund_id, indicator_id, fiscal_year_id):
    # Create a session
    session = create_session()

    # Fetch the last existing fiscal year data from grant_info table
    last_fiscal_year_info = (
        session.query(GrantInfo)
        .filter(            GrantInfo.trustfund_id == trustfund_id, 
            GrantInfo.field == "custom_indicators", 
            GrantInfo.fiscal_year_id != fiscal_year_id)
        .order_by(GrantInfo.fiscal_year_id.desc())
        .first()
    )

    if not last_fiscal_year_info:
        session.close()
        return

    # Parse the JSON data from the deliverable entry
    try:
        all_indicators_data = eval(last_fiscal_year_info.value)
    except:
        st.write("Error parsing indicator data from previous fiscal year.")
        session.close()
        return
    
    # Extract the specific deliverable data
    specific_indicator = all_indicators_data.get(str(indicator_id), {})
    
    if not specific_indicator:
        # This specific deliverable doesn't exist in the previous fiscal year
        session.close()
        return
    
    # Extract the relevant information for display
    target_value = specific_indicator.get('target_value', '')
    input_value = specific_indicator.get('input_value', '')

    # Create a list for display
    indicator_display = [{
        "Fiscal Year": last_fiscal_year_info.fiscal_year,
        "Target Value": target_value,
        "Input Value": input_value,
    }]


    # Convert the list of dictionaries to a DataFrame
    indicator_df = pd.DataFrame(indicator_display)

    # Convert any columns to standard types, if necessary
    indicator_df['Fiscal Year'] = indicator_df['Fiscal Year'].astype(str)

    # Display the data in a table format
    st.write("### Previous Fiscal Year Indicator")
    #st.table(deliverable_display)
    st.dataframe(indicator_df, use_container_width=True, hide_index=True)

    # Close the session
    session.close()


def get_previous_fiscal_year_indicators(trustfund_id, indicator_id, fiscal_year_id):
    # Create a session
    session = create_session()

    # Fetch the last existing fiscal year data from grant_info table
    last_fiscal_year_info = (
        session.query(GrantInfo)
        .filter(            
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.field == "custom_indicators",
            GrantInfo.fiscal_year_id != fiscal_year_id)
        .order_by(GrantInfo.fiscal_year_id.desc())
        .first()
    )

    if not last_fiscal_year_info:
        session.close()
        return None  # No indicators found

    # Parse the deliverables data from JSON
    try:
        all_indicators_data = eval(last_fiscal_year_info.value)
    except:
        session.close()
        return None  # Error parsing data
    
    # Check if the specified deliverable_id exists in the deliverables data
    if str(indicator_id) in all_indicators_data:
        session.close()

        return all_indicators_data[str(indicator_id)]
    else:
        session.close()
        return None  # No deliverable found for the specified deliverable_id


def custom_indicators():
    st.success("### 6. Results Indicators")

    # Create a session
    session = create_session()

    # Fetch existing indicators based on current trustfund_id and fiscal_year_id
    existing_grant_info = session.query(GrantInfo).filter_by(
        trustfund_id=st.session_state.current_trustfund_id, fiscal_year_id=st.session_state.current_fiscal_year_id, deleted=False).first()

    trustfund = session.query(TrustFund).filter(TrustFund.name == current_username(),
                                                TrustFund.team_id == current_team_id()
                                                ).first()

    if trustfund:
        trustfund_id = trustfund.id
    else:
        st.error(f"No TrustFund found for this user - {current_username()}")
        return

    # Fetch all mapping entries for the current trustfund_id
    mappings = session.query(TrustFundIndicatorMapping).filter(
        TrustFundIndicatorMapping.trustfund_id == trustfund_id).all()

    # Check if there are no mappings
    if not mappings:
        st.write(
            f"No indicators found for the provided Trust Fund - {trustfund.name}")
        return

    # Initialize a dictionary to hold input values for all indicators
    custom_indicators_data = {}

    # Check if there is existing data in the indicators column and parse it
    if existing_grant_info:
        long_format_entries = session.query(GrantInfo).filter_by(
            trustfund_id=trustfund_id,
            fiscal_year_id=existing_grant_info.fiscal_year_id,
            deleted=False
        ).all()

        for entry in long_format_entries:
            if entry.field.startswith("custom_indicators"):
                custom_indicators_data = ast.literal_eval(entry.value)

    # Store initial values in session state for change detection
    if 'custom_indicators_initial_values' not in st.session_state:
        st.session_state.custom_indicators_initial_values = {
            str(mapping.indicator_id): {
                "input_value": custom_indicators_data.get(str(mapping.indicator_id), {}).get("input_value", None), 
                "baseline_value": custom_indicators_data.get(str(mapping.indicator_id), {}).get("baseline_value", ""),
                "year_baseline": custom_indicators_data.get(str(mapping.indicator_id), {}).get("year_baseline", None),
                "progress": custom_indicators_data.get(str(mapping.indicator_id), {}).get("progress", ""),
                "target_value": custom_indicators_data.get(str(mapping.indicator_id), {}).get("target_value", ""),
                "year_target": custom_indicators_data.get(str(mapping.indicator_id), {}).get("year_target", None),
                "data_collection": custom_indicators_data.get(str(mapping.indicator_id), {}).get("data_collection", ""),
                "level_of_result": custom_indicators_data.get(str(mapping.indicator_id), {}).get("level_of_result", None)


                }
            for mapping in mappings if str(mapping.indicator_id) in custom_indicators_data.keys()
        }

        # Initialize unsaved changes flag
        st.session_state.custom_indicators_unsaved_changes = False
    else:
        # If initial values already exist, use them
        st.session_state.custom_indicators_initial_values = {
            str(mapping.indicator_id): {
                "input_value": custom_indicators_data.get(str(mapping.indicator_id), {}).get("input_value", None), 
                "baseline_value": custom_indicators_data.get(str(mapping.indicator_id), {}).get("baseline_value", ""),
                "year_baseline": custom_indicators_data.get(str(mapping.indicator_id), {}).get("year_baseline", None),
                "progress": custom_indicators_data.get(str(mapping.indicator_id), {}).get("progress", ""),
                "target_value": custom_indicators_data.get(str(mapping.indicator_id), {}).get("target_value", ""),
                "year_target": custom_indicators_data.get(str(mapping.indicator_id), {}).get("year_target", None),
                "data_collection": custom_indicators_data.get(str(mapping.indicator_id), {}).get("data_collection", ""),
                "level_of_result": custom_indicators_data.get(str(mapping.indicator_id), {}).get("level_of_result", None)
            }
            for mapping in mappings if str(mapping.indicator_id) in custom_indicators_data.keys()
        }
    # Initialize a list to hold missing mandatory fields
    missing_mandatory_fields = []

    # Iterate through each mapping and display appropriate input fields
    for mapping in mappings:
        indicator = session.query(Indicator).filter(
            Indicator.id == mapping.indicator_id, Indicator.custom_indicator == True).first()

        if indicator:
            mandatory_char = ""
            if mapping.relation_ship == "Mandatory":
                mandatory_char = "*"


            input_value = custom_indicators_data.get(str(mapping.indicator_id), {}).get("input_value", None)
            baseline_value = custom_indicators_data.get(str(mapping.indicator_id), {}).get("baseline_value", "")
            year_baseline = custom_indicators_data.get(str(mapping.indicator_id), {}).get("year_baseline", None)
            progress = custom_indicators_data.get(str(mapping.indicator_id), {}).get("progress", "")
            target_value = custom_indicators_data.get(str(mapping.indicator_id), {}).get("target_value", "")
            year_target = custom_indicators_data.get(str(mapping.indicator_id), {}).get("year_target", None)
            data_collection = custom_indicators_data.get(str(mapping.indicator_id), {}).get("data_collection", "")
            level_of_result = custom_indicators_data.get(str(mapping.indicator_id), {}).get("level_of_result", None)


            # Fetch previous fiscal year indicators
            previous_indicators = get_previous_fiscal_year_indicators(trustfund_id, mapping.indicator_id, st.session_state.current_fiscal_year_id)

            # If previous fiscal year deliverables exist, use them to pre-fill the fields
            if previous_indicators:
                previous_baseline_value = previous_indicators.get('baseline_value', '')
                previous_year_baseline = previous_indicators.get('year_baseline', None)
                previous_target_value = previous_indicators.get('target_value', '')
                previous_year_target = previous_indicators.get('year_target', None)   
                previous_data_collection = previous_indicators.get('data_collection', '')
                previous_level_of_result = previous_indicators.get('level_of_result', None)
                previous_input_value = previous_indicators.get('input_value', None)
           
                
                # Use previous values only if existing values are empty
                if not baseline_value:
                    baseline_value = previous_baseline_value
                if not year_baseline:
                    year_baseline = previous_year_baseline
                if not target_value:
                    target_value = previous_target_value
                if not year_target:
                    year_target = previous_year_target
                if not data_collection:
                    data_collection = previous_data_collection
                if not level_of_result:
                    level_of_result = previous_level_of_result
                if not input_value:
                    input_value = previous_input_value

            if mapping.indicator_id not in st.session_state.custom_indicators_initial_values:
            # Store initial values for change tracking
                st.session_state.custom_indicators_initial_values[str(mapping.indicator_id)] = {
                    "input_value": input_value if input_value else None,
                    "baseline_value": baseline_value if baseline_value else '',
                    "year_baseline": year_baseline if year_baseline else None,
                    "progress": progress,
                    "target_value": target_value,
                    "year_target": year_target if year_target else None,
                    "data_collection": data_collection,
                    "level_of_result": level_of_result if level_of_result else None
                }
            else:
                # Update existing entry in initial values
                st.session_state.custom_indicators_initial_values[str(mapping.indicator_id)].update({
                    "input_value": input_value if input_value else None,
                    "baseline_value": baseline_value if baseline_value else '',
                    "year_baseline": year_baseline if year_baseline else None,
                    "progress": progress,
                    "target_value": target_value,
                    "year_target": year_target if year_target else None,
                    "data_collection": data_collection,
                    "level_of_result": level_of_result if level_of_result else None
                })

            with st.expander(indicator.indicator_name):

                show_previous_fiscal_year_indicators(trustfund_id, mapping.indicator_id, st.session_state.current_fiscal_year_id)
                # Include a placeholder option for None
                options = ["Outcome", "Intermediate Outcome", "Output"]

                # Set the index to 0 (the placeholder) if level_of_result is None
                default_index = None if level_of_result is None else options.index(level_of_result)

                level_of_result = st.selectbox(
                    "Level of result",
                    options,
                    index=default_index,
                    key=f"level_of_result_{mapping.id}"
                )

                # Display input fields based on unit_of_measurement
                if indicator.unit_of_measurement == 'Date':
                    input_value = st.date_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"date_input_{mapping.id}")
                elif indicator.unit_of_measurement == 'Number' or indicator.unit_of_measurement == 'Percentage':
                    input_value = st.number_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"number_input_{mapping.id}")
                elif indicator.unit_of_measurement == 'Short Text':
                    input_value = st.text_input(
                        f"{indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"short_text_input_{mapping.id}", placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                elif indicator.unit_of_measurement == 'Long Text':
                    input_value = st.text_area(
                        f"{indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"long_text_input_{mapping.id}", placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                # elif indicator.unit_of_measurement == 'Percentage':
                #     input_value = st.number_input(
                #         f"{mandatory_char}{indicator.indicator_prompt}", value=input_value,  key=f"percentage_input_{mapping.id}")
                elif indicator.unit_of_measurement == 'Categorical':
                    # Read categories from the categorical_unit column and split by ','
                    if indicator.categorical_unit:
                        categories = [cat.strip()
                                      for cat in indicator.categorical_unit.split(',')]
                    else:
                        categories = []  # Handle the case where categorical_unit is None or empty

                    # Display the select box with dynamically loaded categories
                    input_value = st.selectbox(
                        f"{'Progress value: '} {indicator.indicator_prompt} {mandatory_char}", categories, index=categories.index(input_value) if input_value in categories else None, key=f"categorical_input_{mapping.id}"
                    )
                else:
                    st.write("No valid unit of measurement provided.")
                    continue

                baseline_value = st.text_input(
                    "Baseline value", value=baseline_value,
                    key=f"baseline_value_{mapping.id}"
                )

                year_baseline = st.number_input(
                    "Year baseline data was collected", value=year_baseline, min_value=1900, max_value=2100,
                    key=f"year_baseline_{mapping.id}"
                )

                progress = st.text_area(
                    "Explain the Progress",
                    value=progress,
                    key=f"progress_{mapping.id}"
                )

                target_value = st.text_input(
                    "Target value",
                    value=target_value, 
                    key=f"target_value_{mapping.id}"
                )

                year_target = st.number_input(
                    "Year target data will be collected",
                    value=year_target, min_value=1900, max_value=2100,
                    key=f"year_target_{mapping.id}"
                )

                data_collection = st.text_area(
                    "How are you collecting the data?",
                    value=data_collection,
                    placeholder="Where do you obtain the data from? Data source must be publicly available. e.g., Progress Report (PR); Activity Completion Summary (ACS); Implementation Status and Results Report (ISR); Implementation Completion and Results Report (ICR); Client website, etc.",
                    key=f"data_collection_{mapping.id}"
                )

            if mapping.indicator_id in custom_indicators_data:
                # Update existing entry
                custom_indicators_data[str(mapping.indicator_id)].update({
                    "input_value": input_value if input_value else None,
                    "baseline_value": baseline_value if baseline_value else '',
                    "year_baseline": year_baseline if year_baseline else None,
                    "progress": progress if progress else '',
                    "target_value": target_value if target_value else '',
                    "year_target": year_target if year_target else None,
                    "data_collection": data_collection if data_collection else '',
                    "level_of_result": level_of_result if level_of_result else None,
                })
            else:
                # Add new entry
                custom_indicators_data[str(mapping.indicator_id)] = {
                    "input_value": input_value if input_value else None,
                    "baseline_value": baseline_value if baseline_value else '',
                    "year_baseline": year_baseline if year_baseline else None,
                    "progress": progress if progress else '',
                    "target_value": target_value if target_value else '',
                    "year_target": year_target if year_target else None,
                    "data_collection": data_collection if data_collection else '',
                    "level_of_result": level_of_result if level_of_result else None,
                }

            # Check if the field is mandatory and ensure it has a value
            # Delete second part if minus numbers are allowed
            if mapping.relation_ship == "Mandatory" and (input_value is None or input_value == "" or (isinstance(input_value, (int, float)) and input_value < 0)):
                missing_mandatory_fields.append(indicator.indicator_prompt)


    # Check for changes in form values
    current_values = custom_indicators_data
    
    # Detect changes by comparing current values with initial values
    changes_detected = False

    for key, value in current_values.items():
        if value != st.session_state.custom_indicators_initial_values.get(str(key), {}):
            changes_detected = True
            break

    # Update unsaved changes flag
    st.session_state.custom_indicators_unsaved_changes = changes_detected


    if st.button("Save", key=f"save_custom_indicator", type="primary"):
        if custom_indicators_data:
            if existing_grant_info:
                if missing_mandatory_fields == []:  # Check if there are missing mandatory fields
                    # Clear existing entries for the current trustfund and fiscal year
                    session.query(GrantInfo).filter(
                        GrantInfo.trustfund_id == existing_grant_info.trustfund_id,
                        GrantInfo.fiscal_year_id == existing_grant_info.fiscal_year_id,
                        GrantInfo.field == "custom_indicators"
                    ).delete(synchronize_session=False)
                    
                    # Save new values in long format using keys as they are
                    new_entry = GrantInfo(
                        trustfund_id=st.session_state.current_trustfund_id,
                        fiscal_year_id=st.session_state.current_fiscal_year_id,
                        field="custom_indicators",
                        value=str(custom_indicators_data),
                        team_id=current_team_id(),
                        deleted=False,
                        created_at=datetime.datetime.now(),
                        updated_at=datetime.datetime.now()
                    )
                    session.add(new_entry)

                    session.commit()
                    # Reset the initial values to the current values after saving
                    st.session_state.custom_indicators_initial_values = current_values
                    st.session_state.custom_indicators_unsaved_changes = False
                    st.success("Custom Indicators saved successfully!")
                else:
                    st.error("Please fill in all mandatory fields: " +
                             ", ".join(missing_mandatory_fields))
            else:
                st.warning(
                    "No Grant Info exists! Please create one in Basic Grant Information subpage")

        else:
            st.error("No custom indicators were captured.")

    # Display notification if there are unsaved changes
    if st.session_state.custom_indicators_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    session.close()


def all_grants():
    # Set current_trustfund_id to None when focus lost from New grant reporting page
    st.session_state.current_trustfund_id = None
    st.session_state.current_fiscal_year_id = None
    st.success("### All results")
    data = read_data()
    # Create a session
    session = create_session()

    try:
        current_user = session.query(User).filter_by(
            id=st.session_state.user_id).first()
        if current_user is None:
            st.error("User not found.")
            return
        team_id = current_user.team_id

        current_trustfund = session.query(TrustFund).filter(
            TrustFund.team_id == team_id, TrustFund.name == current_user.username).first()

        if current_trustfund is None:
            st.error("Trust Fund not found.")
            return
        current_trustfund_id = current_trustfund.id

        # Display existing grants information
        grants_info = session.query(GrantInfo).filter(
            GrantInfo.team_id == team_id, GrantInfo.deleted == False, GrantInfo.trustfund_id == current_trustfund_id).all()

        if grants_info:

            filtered_grant_infos = grants_info  # No filtering applied for now

            # Create a dictionary to group grant info by trust fund and fiscal year
            grouped_grants = {}
            for grant_info in filtered_grant_infos:
                key = (grant_info.trustfund.id, grant_info.fiscal_year_id)  # Use a tuple as a key
                if key not in grouped_grants:
                    grouped_grants[key] = []
                grouped_grants[key].append(grant_info)

                        
            # Iterate over the grouped grants with index
            for grant_info_indx, ((trustfund_id, fiscal_year_id), grant_info_list) in enumerate(grouped_grants.items()):
                trustfund_name = grant_info_list[0].trustfund.name if grant_info_list[0].trustfund else ''
                fiscal_year = grant_info_list[0].fiscal_year.fy if grant_info_list[0].fiscal_year else ''
                
                grant_info_display = f"Grant ID: {trustfund_name} | Fiscal Year: {fiscal_year}"

                with st.expander(grant_info_display):
<<<<<<< HEAD
                    #for grant_info_indx, grant_info in enumerate(grant_info_list):
                        st.markdown(
                            f"[1. Basic Grant Information](#section-1-{grant_info_indx})")
                        st.markdown(
                            f"[2. Strategic Objective & Progress](#section-2-{grant_info_indx}))")
                        st.markdown(
                            f"[3. Operations Informed and Country Engagements Informed by F4D](#section-3-{grant_info_indx}))")
                        st.markdown(
                            f"[4. Collaboration/Partnership](#section-4-{grant_info_indx})")
                        st.markdown(
                            f"[5. Outputs/deliverables](#section-5-{grant_info_indx})")
                        st.markdown(
                            f"[6. Results Indicators](#section-6-{grant_info_indx})")
                        
                        st.subheader("1. Basic Grant Information",
                                    anchor=f"section-1-{grant_info_indx}")
=======
                    _sec_tabs = st.tabs([
                        "1. Basic Grant Information",
                        "2. Strategic Objective & Progress",
                        "3. Lending Operations",
                        "4. Collaboration/Partnership",
                        "5. Outputs/Deliverables",
                        "6. Results Indicators",
                    ])
                    with _sec_tabs[0]:
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                        
                        # Helper function to get field value from long format
                        def get_field_value(grant_info_list, field_name):
                            for item in grant_info_list:
                                if item.field == field_name:
                                    return item.value.strip() if item.value else None
                            return None
                        
                        # Display trust fund (disabled)
                        new_grant_info = st.text_input(
                            f"Trust Fund", value=grant_info.trustfund.name, key=f"grant_info_{grant_info_indx}", disabled=True)

                        # Fiscal Year selection (disabled)
                        current_fiscal_year_id = grant_info_list[0].fiscal_year_id if grant_info_list[0].fiscal_year_id else None

                        new_fiscal_year = st.selectbox(
                            "Fiscal Year",
                            ["Select a fiscal year"] + [option[0]
                                                        for option in data["fiscal_years"]],
                            index=None if not current_fiscal_year_id else next(i for i, option in enumerate(
                                data["fiscal_years"], 1) if option[1] == current_fiscal_year_id), key=f"fiscal_year_{grant_info_indx}", disabled=True
                        )

                        # Extract fiscal_year_id based on the selection
                        for fy in data["fiscal_years"]:
                            if fy[0] == new_fiscal_year:
                                new_fiscal_year_id = fy[1]
                                break
                        
                        # P code instrument - already adapted
                        current_p_code_instrument = get_field_value(grant_info_list, "p_code_instrument")
                        new_pcode_instrument = st.selectbox(
                            "P code instrument", 
                            ["ASA", "IPF", "PforR", "DPF", "Other"],
                            index=["ASA", "IPF", "PforR", "DPF", "Other"].index(current_p_code_instrument) if current_p_code_instrument in ["ASA", "IPF", "PforR", "DPF", "Other"] else 0,
                            key=f"p_code_instrument_{grant_info_indx}"
                        )

                        # Check if "Other" is selected
                        if new_pcode_instrument == "Other":
                            current_p_code_description = get_field_value(grant_info_list, "p_code_description")
                            new_pcode_description = st.text_input(
                                "If other, please describe:", 
                                value=current_p_code_description or "", 
                                key=f"other_{grant_info_indx}"
                            )
                        else:
                            new_pcode_description = None


                        current_f4d_association = get_field_value(grant_info_list, "f4d_association")

                        # Normalize the value
                        normalized_association = current_f4d_association.strip() if current_f4d_association else None

                        # Create a list of associations from the enum
                        association_values = [association.value for association in F4DAssociationEnum]

                        # Check and get the index safely
                        if normalized_association in association_values:
                            index = association_values.index(normalized_association)
                        else:
                            index = 0  # Default to the first option if not found

                        new_f4d_association = st.selectbox(
                            "F4D Association",
                            association_values,
                            index=index,
                            key=f"f4d_assoc_{grant_info_indx}"
                        )

                        # Region - adapted for long format
                        current_region_id = get_field_value(grant_info_list, "region_id")
                        region = st.selectbox(
                            "Region",
                            ["Select a region"] + [option[0]
                                                for option in data["regions"]],
                            index=None if not current_region_id else next(i for i, option in enumerate(
                                data["regions"], 1) if str(option[1]) == str(current_region_id)),
                            key=f"region_{grant_info_indx}_{grant_info.fiscal_year_id}")

                        # Extract region_id based on the selection
                        new_region_id = None
                        for reg in data["regions"]:
                            if reg[0] == region:
                                new_region_id = reg[1]
                                break

                        # Country selection - adapted for long format
                        current_country = get_field_value(grant_info_list, "country")
                        default_countries = current_country.split(', ') if current_country else []
                        new_country = st.multiselect(
                            "Country/Countries", [c[0] for c in data["countries"]],
                            default=default_countries,
                            key=f"country_{grant_info_indx}_{grant_info.fiscal_year_id}"
                        )

                        # Pillars - adapted for long format
                        current_pillars = get_field_value(grant_info_list, "pillars")
                        default_pillars = current_pillars.split(', ') if current_pillars else []
                        new_pillars = st.multiselect("Select the pillar(s) this grant contributes to:",
                                                    ["Pillar 1: Strengthening Financial Sector Resiliency",
                                                    "Pillar 2: Financing the Poor and Vulnerable",
                                                    "Pillar 3: Financing the Real Economy",
                                                    "Pillar 4: Developing Financial Markets"],
                                                    default=default_pillars,
                                                    key=f"pillars_{grant_info.fiscal_year_id}_{grant_info_indx}"
                                                    )

                        # CCTs - adapted for long format
                        current_ccts = get_field_value(grant_info_list, "ccts")
                        default_ccts = current_ccts.split(', ') if current_ccts else []
                        new_ccts = st.multiselect("Select the cross-cutting theme(s) this grant contributes to and explain how:",
                                                ["Climate change and sustainable finance",
                                                "Advancing digitalization",
                                                "Financing solutions to close gender gaps"],
                                                default=default_ccts,
                                                key=f"ccts_{grant_info.fiscal_year_id}_{grant_info_indx}")

                        # Pillar explanations - adapted for long format
                        current_pillar_explanations = get_field_value(grant_info_list, "pillar_explanations")
                        pillar_explanations = {}
                        if current_pillar_explanations:
                            try:
                                pillar_explanations = ast.literal_eval(current_pillar_explanations)
                            except (ValueError, SyntaxError) as e:
                                st.error("Error parsing pillar explanations. Please check the data format.")

                        # Pillar explanations with pre-filled data if existing data is present
                        for ind, pillar in enumerate(new_pillars):
                            explanation = st.text_area(
                                f"Explain how it contributes to {pillar}",
                                key=f"{pillar}_{grant_info_indx}_{ind}",
                                value=pillar_explanations.get(pillar, "")
                            )
                            pillar_explanations[pillar] = explanation

                        # CCT explanations - adapted for long format
                        current_cct_explanations = get_field_value(grant_info_list, "cct_explanations")
                        cct_explanations = {}
                        if current_cct_explanations:
                            try:
                                cct_explanations = ast.literal_eval(current_cct_explanations)
                            except (ValueError, SyntaxError) as e:
                                st.error("Error parsing CCT explanations. Please check the data format.")

                        # CCT explanations with pre-filled data if existing data is present
                        for i, cct in enumerate(new_ccts):
                            explanation = st.text_area(
                                f"Explain how it contributes to {cct}",
                                key=f"{cct}_{grant_info_indx}_{i}",
                                value=cct_explanations.get(cct, "")
                            )
                            cct_explanations[cct] = explanation

<<<<<<< HEAD
                        st.subheader("2. Strategic Objective & Progress", anchor=f"section-2-{grant_info_indx}")
=======
                    with _sec_tabs[1]:
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)

                        # Overall progress - adapted for long format
                        current_overall_progress = get_field_value(grant_info_list, "overall_progress")
                        new_overall_progress = st.text_area(
                            "Overall progress since inception",
                            value=current_overall_progress or "",
                            key=f"overall_progress_{grant_info_indx}",
                            placeholder="Please provide a short summary of the overall progress since inception of the grant towards achieving the strategic objective, with a focus on progress towards outcomes instead of listing deliverables. Include details including developments in client support/interest, coordination and partnerships with other donors, development partners and/or other WB units and IFC; include any relevant lessons learned."
                        )
                        
                        # Implementation challenges - adapted for long format
                        current_implementation_challenges = get_field_value(grant_info_list, "implementation_challenges")
                        new_implementation_challenges = st.text_area(
                            "Implementation Challenges",
                            value=current_implementation_challenges or "",
                            key=f"implementation_challenges_{grant_info_indx}",
                            placeholder="Please provide any challenges faced so far, any external or unexpected events that affect the implementation or results."
                        )
                        
                        # Public communication external - adapted for long format
                        current_public_communication_external = get_field_value(grant_info_list, "public_communication_external")
                        new_public_communication_external = st.text_area(
                            "Public communication (external)",
                            value=current_public_communication_external or "",
                            key=f"public_communication_external_{grant_info_indx}",
                            placeholder="List external public communications that took place. Examples include a link to a press release, an external conference, counterpart quotes, newspaper, journals, articles, blogs, website, data infographics, brochures, booklet, reports, TV, YouTube video, photos, etc. Send files at attachments if there is no link."
                        )
                        
                        # Public communication internal - adapted for long format
                        current_public_communication_internal = get_field_value(grant_info_list, "public_communication_internal")
                        new_public_communication_internal = st.text_area(
                            "Public communication (internal)",
                            value=current_public_communication_internal or "",
                            key=f"public_communication_internal_{grant_info_indx}",
                            placeholder="List any World Bank intranet appearances (such as links to blog posts, feature stories, Up Front story, photos of internal events, data infographics, etc.). Send files at attachments to financefordevelopment@worldbank.org if there is no link."
                        )

<<<<<<< HEAD
                        st.subheader("3. Operations Informed and Country Engagements Informed by F4D", anchor=f"section-3-{grant_info_indx}")
=======
                    with _sec_tabs[2]:
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                        # Create a unique session key for operations based on grant_info
                        operation_session_key = f"operation_{grant_info_indx}_{grant_info.fiscal_year_id}"

                        # Initialize session state for operations if not already present
                        if operation_session_key not in st.session_state:
                            st.session_state[operation_session_key] = []

                        # Initialize operations list if not already in session state
                        if not st.session_state[operation_session_key]:
                            st.session_state[operation_session_key] = []

                            # Iterate through operation fields in the grant_info_list
                            operation_index = 1
                            while True:
                                operation_field = f'operation_{operation_index}'
                                
                                # Check if the field exists in the grant_info_list
                                current_operation = get_field_value(grant_info_list, operation_field)
                                
                                # Break the loop if the operation field does not exist or is empty
                                if not current_operation:
                                    break
                                
                                # Assuming current_operation is a string representation of a dictionary
                                try:
                                    operation_data = eval(current_operation)  # Use eval only if you trust the source
                                    st.session_state[operation_session_key].append({
                                        "informed_operation": operation_data.get('informed_operation'),
                                        "p_number": operation_data.get('p_number'),
                                        "p_code_instrument": operation_data.get('p_code_instrument'),
                                        "p_code_instrument_description": operation_data.get('p_code_instrument_description'),
                                        "approval_fy": operation_data.get('approval_fy'),
                                        "operation_name": operation_data.get('operation_name'),
                                        "total_commitment": operation_data.get('total_commitment'),
                                        "informed_by_f4d": operation_data.get('informed_by_f4d'),
                                        "evidence": operation_data.get('evidence')
                                    })
                                except Exception as e:
                                    st.error(f"Error processing {operation_field}: {e}")
                                
                                operation_index += 1



                        # Variable to hold the index of the operation to delete
                        operation_to_delete = None

                        # Display the input fields for each operation
                        for i, operation in enumerate(st.session_state[operation_session_key]):
                            st.subheader(f"Operation {i + 1}")

                            operation['informed_operation'] = st.radio(
                                "Did the grant inform a Board approved World Bank lending operation?", [
                                    "Yes", "No"],
                                index=0 if operation['informed_operation'] == "Yes" else 1,
                                key=f"informed_operation_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                            )

                            st.markdown(
                                "F4D will ask the Regional PM to clear the information you will provide below. Please ensure you provide accurate information below.")

                            operation['p_number'] = st.text_input(
                                "P number of the informed operation",
                                value=operation['p_number'],
                                key=f"p_number_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                            )

                            options = ["IPF", "PforR", "DPF", "Other"]

                            # Ensure operation['p_code_instrument'] is initialized as a single value
                            current_p_code_instrument = operation['p_code_instrument'] if operation['p_code_instrument'] else "IPF"  # Default to "IPF"

                            # Use selectbox for single selection
                            operation['p_code_instrument'] = st.selectbox(
                                "P code instrument of the informed operation",
                                options,
                                index=options.index(current_p_code_instrument) if current_p_code_instrument in options else 0,
                                key=f"p_code_instrument_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                            )

                            # Check if "Other" is selected
                            if operation['p_code_instrument'] == "Other":
                                operation['p_code_instrument_description'] = st.text_input(
                                    "If other, please describe:",
                                    value=operation['p_code_instrument_description'],
                                    key=f"p_code_instrument_description_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                                )
                            else:
                                operation['p_code_instrument_description'] = None

                            operation['approval_fy'] = st.text_input(
                                "Approval FY of the informed lending operation",
                                value=operation['approval_fy'],
                                key=f"approval_fy_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                            )

                            operation['operation_name'] = st.text_input(
                                "Operation name",
                                value=operation['operation_name'],
                                key=f"operation_name_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                            )

                            operation['total_commitment'] = st.number_input(
                                "Total commitment amount of the informed operation (in US$ millions)",
                                value=operation['total_commitment'] if operation['total_commitment'] else 0.0,
                                key=f"total_commitment_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}",
                                format="%f"
                            )

                            operation['informed_by_f4d'] = st.number_input(
                                "How much out of the total amount was informed by the F4D grant? (e.g., for the relevant component(s) - in US$ millions)",
                                value=operation['informed_by_f4d'] if operation['informed_by_f4d'] else 0.0,
                                key=f"informed_by_f4d_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}",
                                format="%f"
                            )

                            operation['evidence'] = st.text_area(
                                "EVIDENCE: How did the grant contribute to the lending operation's objective?",
                                placeholder="Describe how the F4D grant informed the operation. Clearly articulate the relevant sections and references to F4D support in a way the information can be verified (e.g., copy-pasting the relevant sections).",
                                value=operation['evidence'],
                                key=f"evidence_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"
                            )

                            col1, col2 = st.columns([2, 2])

                            with col1:
                                # Show the Save button for each operation
                                if st.button(f"Save Operation {i + 1}", key=f"save_operation_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"):
                                    # Create a dictionary to hold operations to save
                                    operations_to_save = {}
                                    
                                    for index, operation_item in enumerate(st.session_state[operation_session_key]):
                                        # Store each operation with its corresponding operation_x key
                                        operations_to_save[f"operation_{index + 1}"] = {
                                            "informed_operation": operation_item['informed_operation'],
                                            "p_number": operation_item['p_number'],
                                            "p_code_instrument": operation_item['p_code_instrument'],
                                            "p_code_instrument_description": operation_item['p_code_instrument_description'],
                                            "approval_fy": operation_item['approval_fy'],
                                            "operation_name": operation_item['operation_name'],
                                            "total_commitment": operation_item['total_commitment'],
                                            "informed_by_f4d": operation_item['informed_by_f4d'],
                                            "evidence": operation_item['evidence']
                                        }

                                    # Save each operation as operation_1, operation_2, etc.
                                    for key, value in operations_to_save.items():
                                        # Find or create the operations record in long format
                                        operations_record = next((g for g in grant_info_list if g.field == key), None)
                                        
                                        if operations_record:
                                            operations_record.value = str(value)  # Update existing record
                                        else:
                                            # Create new record if it doesn't exist
                                            new_operations_record = GrantInfo(
                                                trustfund_id=trustfund_id,
                                                fiscal_year_id=fiscal_year_id,
                                                team_id=grant_info.team_id,
                                                field=key,  # Use the operation_x field
                                                value=str(value),
                                                created_at=datetime.datetime.now(),
                                                updated_at=datetime.datetime.now()
                                            )
                                            session.add(new_operations_record)

                                    session.commit()
                                    st.success(f"Operation {i + 1} saved successfully!")

                            with col2:
                                # Show the Delete button for each operation
                                if st.button(f"Delete Operation {i + 1}", key=f"delete_operation_{grant_info_indx}_{grant_info.fiscal_year_id}_{i}"):
                                    operation_to_delete = i  # Set the index of the operation to delete

                        # Handle deletion outside the loop to avoid index shift issues
                        if operation_to_delete is not None:
                            # Get the field name for the operation to delete
                            operation_field = f"operation_{operation_to_delete + 1}"
                            
                            # Find the existing operations record in long format
                            operations_record = next((g for g in grant_info_list if g.field == operation_field), None)
                            
                            if operations_record:
                                # Delete the operation record from the session
                                session.delete(operations_record)

                                # Optionally, remove the operation from the session state as well
                                st.session_state[operation_session_key].pop(operation_to_delete)

                            session.commit()
                            st.success(f"Operation {operation_to_delete + 1} deleted successfully!")
                            st.rerun()

                        # Button to trigger addition of a new operation
                        if st.button("Add Operation", key=f"add_operation_{grant_info_indx}_{grant_info.fiscal_year_id}"):
                            st.session_state[operation_session_key].append({
                                "informed_operation": "",
                                "p_number": "",
                                "p_code_instrument": [],
                                "p_code_instrument_description": "",
                                "approval_fy": "",
                                "operation_name": "",
                                "total_commitment": "",
                                "informed_by_f4d": "",
                                "evidence": ""
                            })
                            st.rerun()

                        # CPFs - adapted for long format
                        cpf_session_key = f"cpf_{grant_info_indx}_{grant_info.fiscal_year_id}"

                        # Initialize session state for cpfs if not already present
                        if cpf_session_key not in st.session_state:
                            st.session_state[cpf_session_key] = []
                        
                        # Initialize cpfs list if not already in session state                        # Initialize operations list if not already in session state
                        if not st.session_state[cpf_session_key]:
                            st.session_state[cpf_session_key] = []

                        # Only iterate if the session state is empty
                        if not st.session_state[cpf_session_key]:
                            st.session_state[cpf_session_key] = []
                            # Iterate through cpf fields in the grant_info_list
                            cpf_index = 1
                            while True:
                                cpf_field = f'cpf_{cpf_index}'
      
                                # Check if the field exists in the grant_info_list
                                current_cpfs = get_field_value(grant_info_list, cpf_field)
                                # Break the loop if the cpf field does not exist or is empty
                                if not current_cpfs:
                                    break
                                # Assuming current_cpfs is a string representation of a dictionary
                                try:
                                    # Use eval to convert the string representation to a dictionary
                                    current_cpfs = ast.literal_eval(current_cpfs)
                                    st.session_state[cpf_session_key].append({
                                        "informed_cpf": current_cpfs.get('informed_cpf', ''),
                                        "country": current_cpfs.get('country', []),
                                        "year": current_cpfs.get('year', ''),
                                        "evidence": current_cpfs.get('evidence', '')
                                    })
                                except Exception as e:
                                    st.error(f"Error processing {cpf_field}: {e}")
                                
                                cpf_index += 1


                        # Variable to hold the index of CPF to delete
                        cpf_to_delete = None

                        # Display input fields for each CPF
                        for i_cpf, cpf in enumerate(st.session_state[cpf_session_key]):
                            st.subheader(f"CPF {i_cpf + 1}")

                            # Input fields for CPF data
                            cpf['informed_cpf'] = st.radio(
                                "Did the grant inform a CPF?", ["Yes", "No"],
                                index=0 if cpf['informed_cpf'] == "Yes" else 1,
                                key=f"informed_cpf_{grant_info_indx}_{grant_info.fiscal_year_id}_{i_cpf}"
                            )

                            st.markdown(
                                "F4D will ask the Regional PM to clear the information you will provide below. Please ensure you provide accurate information."
                            )

                            # Ensure cpf['country'] is a list
                            if isinstance(cpf['country'], str):
                                default_countries = cpf['country'].split(', ') if cpf['country'] else []
                            else:
                                default_countries = cpf['country'] if isinstance(cpf['country'], list) else []

                            # Sort the countries by name
                            sorted_countries = sorted([c[0] for c in data["countries"]])

                            # Select countries with pre-selection if existing data is present
                            cpf['country'] = st.multiselect(
                                "For which country:", 
                                sorted_countries,
                                default=default_countries,
                                key=f"cpf_country_{grant_info_indx}_{grant_info.fiscal_year_id}_{i_cpf}"
                            )

                            # Read the fiscal year from the selectbox
                            cpf['year'] = st.selectbox(
                                "For which year:",
                                [option[0] for option in data["fiscal_years"]],
                                index=None if not cpf['year'] else next(
                                    (i for i, option in enumerate(data["fiscal_years"], 0) if option[0] == cpf['year']),
                                    0
                                ), key=f"cpf_year_{grant_info_indx}_{grant_info.fiscal_year_id}_{i_cpf}"
                            )

                            cpf['evidence'] = st.text_area(
                                "EVIDENCE: How did the grant contribute to the CPF?",
                                placeholder="Describe how the F4D grant informed the CPF.",
                                value=cpf['evidence'],
                                key=f"cpf_evidence_{grant_info_indx}_{grant_info.fiscal_year_id}_{i_cpf}"
                            )

                            col1, col2 = st.columns([2, 2])

                            with col1:
                                # Save button for each CPF
                                if st.button(f"Save CPF {i_cpf + 1}", key=f"save_cpf_{grant_info_indx}_{grant_info.fiscal_year_id}_{i_cpf}"):
                                    # Prepare CPFs for saving
                                    cpfs_to_save = {}
                                    for index, cpf_item in enumerate(st.session_state[cpf_session_key]):
                                        cpfs_to_save[f"cpf_{index + 1}"] = {
                                            "informed_cpf": cpf_item['informed_cpf'],
                                            "country": cpf_item['country'],
                                            "year": cpf_item['year'],
                                            "evidence": cpf_item['evidence']
                                        }

                                    # Save existing each CPFs as cpf_1, cpf_2, etc.
                                    for key, value in cpfs_to_save.items():
                                        # Find or create the CPFs record in long format
                                        cpfs_record = next((g for g in grant_info_list if g.field == f"cpf_{index + 1}"), None)
                                        if cpfs_record:
                                            cpfs_record.value = str(cpfs_to_save) # Update existing record
                                        else:
                                            # Create new record if it doesn't exist
                                            new_cpfs_record = GrantInfo(
                                                trustfund_id=trustfund_id,
                                                fiscal_year_id=fiscal_year_id,
                                                team_id=grant_info.team_id,
                                                field=key,  # Use the cpf_x field
                                                value=str(value),
                                                created_at=datetime.datetime.now(),
                                                updated_at=datetime.datetime.now()
                                            )
                                            session.add(new_cpfs_record)
                                        
                                        session.commit()
                                        st.success(f"CPF {i_cpf + 1} saved successfully!")

                            with col2:
                                # Delete button for each CPF
                                if st.button(f"Delete CPF {i_cpf + 1}", key=f"delete_cpf_{grant_info_indx}_{grant_info.fiscal_year_id}_{i_cpf}"):
                                    cpf_to_delete = i_cpf  # Set the index of the CPF to delete


                            # Handle deletion outside of loop to avoid index issues
                            if cpf_to_delete is not None:
                                # Get the field name for the CPF to delete
                                cpf_field = f"cpf_{cpf_to_delete + 1}"
                                # Find the existing CPFs record in long format
                                cpfs_record = next((g for g in grant_info_list if g.field == cpf_field), None)
                                if cpfs_record:
                                    # Delete the CPF record from the session
                                    session.delete(cpfs_record)

                                    # Optionally, remove the CPF from the session state as well
                                    st.session_state[cpf_session_key].pop(cpf_to_delete)


                                session.commit()
                                st.success(f"CPF {cpf_to_delete + 1} deleted successfully!")
                                st.rerun()

                        # Button to trigger addition of a new cpf entry
                        if st.button("Add CPF", key=f"add_cpf_{grant_info_indx}"):
                            st.session_state[cpf_session_key].append({
                                "informed_cpf": "",
                                "country": "",
                                "year": "",
                                "evidence": ""
                            })

<<<<<<< HEAD
                        st.subheader("4. Collaboration/Partnership", anchor=f"section-4-{grant_info_indx}")
=======
                    with _sec_tabs[3]:
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)

                        # Get current collaborations from long format
                        current_collaborations_str = get_long_format_value(session, trustfund_id, fiscal_year_id, 'collaborations', '')

                        default_collaborations = ast.literal_eval(current_collaborations_str) if current_collaborations_str else []

                        # Multi-select for collaboration options with default values
                        new_collaborations = st.multiselect(
                            "Is the grant delivered in collaboration/partnership with other World Bank teams (e.g. other GPs), IFC, IMF, or other MDBs/IFIs/bilateral organizations? *", [
                                "Other World Bank teams (e.g. GPs)",
                                "IFC",
                                "IMF",
                                "Other IFIs/MDBs/bilateral organizations",
                                "Other organizations (e.g. CSOs, private sector, academia, think tanks)",
                                "No"   
                            ], default=default_collaborations,
                            key=f"collaborations_{grant_info_indx}_{grant_info.fiscal_year_id}")

                        new_other_teams = ""
                        new_other_ifis = ""
                        new_other_orgs = ""
                        new_describe_collaboration = ""
                        new_lessons_learned = ""

                        # If "Yes" options are selected, ask for additional details
                        if new_collaborations:
                            if "Other World Bank teams (e.g. GPs)" in new_collaborations:
                                current_other_teams = get_long_format_value(session, trustfund_id, fiscal_year_id, 'other_teams', '')
                                new_other_teams = st.text_input(
                                    "Which teams?", value=current_other_teams, key="new_other_teams")

                            if "Other IFIs/MDBs/bilateral organizations" in new_collaborations:
                                current_other_ifis = get_long_format_value(session, trustfund_id, fiscal_year_id, 'other_ifis', '')
                                new_other_ifis = st.text_input(
                                    "Which organizations?", value=current_other_ifis, key="new_other_ifis")

                            if "Other organizations (e.g. CSOs, private sector, academia, think tanks)" in new_collaborations:
                                current_other_orgs = get_long_format_value(session, trustfund_id, fiscal_year_id, 'other_orgs', '')
                                new_other_orgs = st.text_input(
                                    "Which other organizations?", value=current_other_orgs, key="new_other_orgs")

                            if "No" not in new_collaborations:
                                current_describe_collaboration = get_long_format_value(session, trustfund_id, fiscal_year_id, 'describe_collaboration', '')
                                new_describe_collaboration = st.text_area(
                                    "Describe the collaboration",
                                    placeholder="In which areas of the grant is the collaboration taking place/took place? What strengths or value-added by the partners were leveraged in the collaboration/partnership? What role did the World Bank play in the collaboration/partnership?",
                                    value=current_describe_collaboration,
                                    key=f"describe_collaboration_{grant_info_indx}_{grant_info.fiscal_year_id}"
                                )

                                current_lessons_learned = get_long_format_value(session, trustfund_id, fiscal_year_id,  'lessons_learned', '')
                                new_lessons_learned = st.text_area(
                                    "Lessons learned",
                                    placeholder="Please describe any lessons learned from the collaboration. How is the partnership expected to evolve?",
                                    value=current_lessons_learned,
                                    key=f"lessons_learned_{grant_info_indx}_{grant_info.fiscal_year_id}"
                                )

<<<<<<< HEAD
                        st.subheader("5. Outputs/deliverables", anchor=f"section-5-{grant_info_indx}")
=======
                    with _sec_tabs[4]:
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)

                        # Initialize a list to hold missing mandatory fields
                        missing_mandatory_fields = []

                        mappings = session.query(TrustFundIndicatorMapping).filter(
                            TrustFundIndicatorMapping.trustfund_id == trustfund_id).all()

                        # Initialize a dictionary to hold input values for all deliverables
                        new_deliverables_data = {}

                        # Check if there is existing data in the deliverables and parse it
                        current_deliverables_str = get_long_format_value(session, trustfund_id, fiscal_year_id, 'deliverables', '{}')
                        if current_deliverables_str and current_deliverables_str != '{}':
                            try:
                                new_deliverables_data = eval(current_deliverables_str)
                            except:
                                new_deliverables_data = {}

                        j = 0
                        # Iterate through each mapping and display appropriate input fields
                        for mapping in mappings:
                            indicator = session.query(Indicator).filter(
                                Indicator.id == mapping.indicator_id, 
                                Indicator.custom_indicator == False, 
                                Indicator.deleted == False).first()

                            if indicator:
                                j = j + 1
                                mandatory_char = ""
                                if mapping.relation_ship == "Mandatory":
                                    mandatory_char = "*"

                                # Pre-fill the input field with existing data if available
                                if str(mapping.indicator_id) in new_deliverables_data:
                                    existing_data = new_deliverables_data[str(mapping.indicator_id)]
                                    input_value = existing_data.get("input_value")
                                    progress = existing_data.get("progress")
<<<<<<< HEAD
=======
                                    deliverable_quantity = existing_data.get("deliverable_quantity", "")
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                                    description = existing_data.get("description")
                                    data_source = existing_data.get("data_source")
                                    next_steps = existing_data.get("next_steps")
                                    supporting_materials_url = existing_data.get("supporting_materials_url")
                                else:
                                    input_value = None
                                    progress = ""
<<<<<<< HEAD
=======
                                    deliverable_quantity = ""
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                                    description = ""
                                    data_source = ""
                                    next_steps = ""
                                    supporting_materials_url = ""

                                st.write(f"**{indicator.indicator_name.strip()}**")

                                # Display input fields based on unit_of_measurement
                                if indicator.unit_of_measurement == 'Date':
                                    input_value = st.date_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"date_input_{grant_info_indx}_{mapping.id}")
                                elif indicator.unit_of_measurement == 'Number':
                                    input_value = st.number_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"number_input_{grant_info_indx}_{mapping.id}")
                                elif indicator.unit_of_measurement == 'Short Text':
                                    input_value = st.text_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"short_text_input_{grant_info_indx}_{mapping.id}", 
                                        placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                                elif indicator.unit_of_measurement == 'Long Text':
                                    input_value = st.text_area(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"long_text_input_{grant_info_indx}_{mapping.id}", 
                                        placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                                elif indicator.unit_of_measurement == 'Percentage':
                                    input_value = st.number_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"percentage_input_{grant_info_indx}_{mapping.id}")
                                elif indicator.unit_of_measurement == 'Categorical':
                                    # Read categories from the categorical_unit column and split by ','
                                    if indicator.categorical_unit:
                                        categories = [cat.strip() for cat in indicator.categorical_unit.split(',')]
                                    else:
                                        categories = []  # Handle the case where categorical_unit is None or empty

                                    # Display the select box with dynamically loaded categories
                                    input_value = st.selectbox(
<<<<<<< HEAD
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        categories, 
                                        index=categories.index(input_value) if input_value in categories else None, 
=======
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}",
                                        categories,
                                        index=categories.index(input_value) if input_value in categories else None,
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                                        key=f"categorical_input_{grant_info_indx}_{mapping.id}")
                                else:
                                    st.write("No valid unit of measurement provided.")
                                    continue

                                
                                
                                progress = st.text_input(
                                    f"{j} - Number of deliverable(s)",
                                    placeholder="Count the unique number of deliverable(s) ever achieved since the grant activation",
                                    value=progress,
                                    key=f"progress_{grant_info_indx}_{mapping.id}"
                                )

<<<<<<< HEAD
=======
                                deliverable_quantity = st.text_input(
                                    f"{j} - Deliverable quantity",
                                    placeholder="Enter the number or quantity of this deliverable (e.g., number of MSMEs informed, number of reports produced).",
                                    value=deliverable_quantity,
                                    key=f"deliverable_quantity_{grant_info_indx}_{mapping.id}"
                                )

>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                                description = st.text_area(
                                    f"{j} - Brief description of the deliverable(s), including risk of delay",
                                    placeholder="Add detailed information to help the donors understand the details of the deliverable(s), including risk of delay",
                                    value=description,
                                    key=f"description_{grant_info_indx}_{mapping.id}"
                                )

                                data_source = st.text_input(
                                    f"{j} - Data source",
                                    placeholder="Provide link to the extent possible",
                                    value=data_source,
                                    key=f"data_source_{grant_info_indx}_{mapping.id}"
                                )

                                next_steps = st.text_area(
                                    f"{j} - Next steps and any required adjustments in FY",
                                    value=next_steps,
                                    placeholder="Describe any adjustments to the deliverable(s) that will be required going forward",
                                    key=f"next_steps_{grant_info_indx}_{mapping.id}"
                                )

                                supporting_materials_url = st.text_input(
                                    f"{j} - URL(link) of any photos, videos, articles, or related items",
                                    value=supporting_materials_url,
                                    key=f"supporting_materials_url_{grant_info_indx}_{mapping.id}"
                                )

                                # Save the input_value into the deliverables_data dictionary
                                new_deliverables_data[str(mapping.indicator_id)] = {
                                    "input_value": input_value,
                                    "progress": progress,
<<<<<<< HEAD
=======
                                    "deliverable_quantity": deliverable_quantity,
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                                    "description": description,
                                    "data_source": data_source,
                                    "next_steps": next_steps,
                                    "supporting_materials_url": supporting_materials_url,
                                }

                                # Check if the field is mandatory and ensure it has a value
                                if mapping.relation_ship == "Mandatory" and (input_value is None or input_value == "" or (isinstance(input_value, (int, float)) and input_value < 0)):
                                    missing_mandatory_fields.append(indicator.indicator_prompt)
                                # Uncomment to make this field "Number of deliverable(s)" mandatory
                                # if progress is None or progress == "":
                                #     missing_mandatory_fields.append("Number of deliverable(s)")

<<<<<<< HEAD
                        st.subheader("6. Results Indicators", anchor=f"section-6-{grant_info_indx}")
=======
                    with _sec_tabs[5]:
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)

                        # Initialize a dictionary to hold input values for all indicators
                        new_custom_indicators_data = {}

                        # Check if there is existing data in the custom indicators and parse it
                        current_custom_indicators_str = get_long_format_value(session, trustfund_id, fiscal_year_id, 'custom_indicators', '{}')

                        if current_custom_indicators_str and current_custom_indicators_str != '{}':
                            try:
                                new_custom_indicators_data = eval(current_custom_indicators_str)
                            except Exception as e:
                                print(f"Error parsing custom indicators: {e}")
                                new_custom_indicators_data = {}

                        # Initialize a list to hold missing mandatory fields
                        custom_missing_mandatory_fields = []
                        j = 0
                        # Iterate through each mapping and display appropriate input fields
                        for mapping in mappings:
                            indicator = session.query(Indicator).filter(
                                Indicator.id == mapping.indicator_id, 
                                Indicator.custom_indicator == True, 
                                Indicator.deleted == False).first()

                            if indicator:
                                j = j + 1
                                mandatory_char = ""
                                if mapping.relation_ship == "Mandatory":
                                    mandatory_char = "*"

                                # Pre-fill the input field with existing data if available
                                if str(mapping.indicator_id) in new_custom_indicators_data:
                                    existing_data = new_custom_indicators_data[str(mapping.indicator_id)]
                                    input_value = existing_data.get("input_value")
                                    baseline_value = existing_data.get("baseline_value")
                                    year_baseline = existing_data.get("year_baseline")
                                    progress = existing_data.get("progress")
                                    target_value = existing_data.get("target_value")
                                    year_target = existing_data.get("year_target")
                                    data_collection = existing_data.get("data_collection")
                                    level_of_result = existing_data.get("level_of_result")
                                else:
                                    input_value = None
                                    baseline_value = ""
                                    year_baseline = None
                                    progress = ""
                                    target_value = ""
                                    year_target = None
                                    data_collection = ""
                                    level_of_result = None

                                # Pre-fill the input field with existing data if available
                                if str(mapping.indicator_id) in new_custom_indicators_data:
                                    input_value = new_custom_indicators_data[str(mapping.indicator_id)]["input_value"]
                                else:
                                    input_value = None


                                st.write(f"**{indicator.indicator_name.strip()}**")
                                
                                # Include a placeholder option for None
                                ind_options = ["Outcome", "Intermediate Outcome", "Output"]

                                # Set the index to 0 (the placeholder) if level_of_result is None
                                ind_default_index = None if level_of_result is None else ind_options.index(level_of_result)

                                level_of_result = st.selectbox(
                                    f"{j} - Level of result",
                                    ind_options,
                                    index=ind_default_index,
                                    key=f"level_of_result_{grant_info_indx}_{mapping.id}"
                                )

                                # Display input fields based on unit_of_measurement
                                if indicator.unit_of_measurement == 'Date':
                                    input_value = st.date_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"date_input_{grant_info_indx}_{mapping.id}")
                                elif indicator.unit_of_measurement == 'Number' or indicator.unit_of_measurement == 'Percentage':
                                    input_value = st.number_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"number_input_{grant_info_indx}_{mapping.id}")
                                elif indicator.unit_of_measurement == 'Short Text':
                                    input_value = st.text_input(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"short_text_input_{grant_info_indx}_{mapping.id}", 
                                        placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                                elif indicator.unit_of_measurement == 'Long Text':
                                    input_value = st.text_area(
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                        value=input_value, 
                                        key=f"long_text_input_{grant_info_indx}_{mapping.id}", 
                                        placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                                # elif indicator.unit_of_measurement == 'Percentage':
                                #     input_value = st.number_input(
                                #         f"{j} - {indicator.indicator_prompt} {mandatory_char}", 
                                #         value=input_value, 
                                #         key=f"percentage_input_{grant_info.id}_{mapping.id}")
                                elif indicator.unit_of_measurement == 'Categorical':
                                    # Read categories from the categorical_unit column and split by ','
                                    if indicator.categorical_unit:
                                        categories = [cat.strip() for cat in indicator.categorical_unit.split(',')]
                                    else:
                                        categories = []  # Handle the case where categorical_unit is None or empty

                                    # Display the select box with dynamically loaded categories
                                    input_value = st.selectbox(
                                        f"{j} - {'Progress value: '} {indicator.indicator_prompt} {mandatory_char}", 
                                        categories, 
                                        index=categories.index(input_value) if input_value in categories else 0, 
                                        key=f"categorical_input_{grant_info_indx}_{mapping.id}")
                                else:
                                    st.write("No valid unit of measurement provided.")
                                    continue

                                baseline_value = st.text_input(
                                    f"{j} - Baseline value", 
                                    value=baseline_value,
                                    key=f"baseline_value_{grant_info_indx}_{mapping.id}"
                                )

                                year_baseline = st.number_input(
                                    f"{j} - Year baseline data was collected", 
                                    value=year_baseline if year_baseline else None, 
                                    min_value=1900, 
                                    max_value=2100,
                                    key=f"year_baseline_{grant_info_indx}_{mapping.id}"
                                )

                                progress = st.text_area(
                                    f"{j} - Explain the Progress",
                                    value=progress,
                                    key=f"progress_{grant_info_indx}_{mapping.id}"
                                )

                                target_value = st.text_input(
                                    f"{j} - Target value",
                                    value=target_value,
                                    key=f"target_value_{grant_info_indx}_{mapping.id}"
                                )

                                year_target = st.number_input(
                                    f"{j} - Year target data will be collected",
                                    value=year_target if year_target else None, 
                                    min_value=1900, 
                                    max_value=2100,
                                    key=f"year_target_{grant_info_indx}_{mapping.id}"
                                )

                                data_collection = st.text_area(
                                    f"{j} - How are you collecting the data?",
                                    value=data_collection,
                                    placeholder="Where do you obtain the data from? Data source must be publicly available. e.g., Progress Report (PR); Activity Completion Summary (ACS); Implementation Status and Results Report (ISR); Implementation Completion and Results Report (ICR); Client website, etc.",
                                    key=f"data_collection_{grant_info_indx}_{mapping.id}"
                                )

                                # Save the input_value into the custom_indicators_data dictionary
                                new_custom_indicators_data[str(mapping.indicator_id)] = {
                                    "level_of_result": level_of_result,
                                    "input_value": input_value,
                                    "baseline_value": baseline_value,
                                    "year_baseline": year_baseline,
                                    "progress": progress,
                                    "target_value": target_value,
                                    "year_target": year_target,
                                    "data_collection": data_collection,
                                }

                                # Check if the field is mandatory and ensure it has a value
                                if mapping.relation_ship == "Mandatory" and (input_value is None or input_value == "" or (isinstance(input_value, (int, float)) and input_value < 0)):
                                    custom_missing_mandatory_fields.append(indicator.indicator_prompt)

<<<<<<< HEAD
                        # Create 2 columns for buttons
                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("Update", key=f"update_{grant_info_indx}_{grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}"):
=======
                    # Update/Delete buttons appear below tabs, accessible from any section
                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button("Update", key=f"update_{grant_info_indx}_{grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}"):
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
                                if missing_mandatory_fields == []:
                                    if custom_missing_mandatory_fields == []:
                                        # Update all fields in long format
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'country', ', '.join(new_country))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'p_code_instrument', new_pcode_instrument)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'p_code_description', new_pcode_description)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'f4d_association', new_f4d_association)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'region_id', str(new_region_id))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'pillars', ', '.join(new_pillars))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'ccts', ', '.join(new_ccts))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'pillar_explanations', str(pillar_explanations))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'cct_explanations', str(cct_explanations))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'overall_progress', new_overall_progress)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'implementation_challenges', new_implementation_challenges)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'public_communication_external', new_public_communication_external)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'public_communication_internal', new_public_communication_internal)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'collaborations', str(new_collaborations))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'other_teams', new_other_teams)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'other_ifis', new_other_ifis)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'other_orgs', new_other_orgs)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'describe_collaboration', new_describe_collaboration)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'lessons_learned', new_lessons_learned)
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'deliverables', str(new_deliverables_data))
                                        update_long_format_field(session, trustfund_id, fiscal_year_id, 'custom_indicators', str(new_custom_indicators_data))
                                        
                                        st.success(f"Updated Grant: {grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}")
                                    else:
                                        st.warning("Please fill in all mandatory fields of custom indicators: " + ", ".join(custom_missing_mandatory_fields))
                                else:
                                    st.warning("Please fill in all mandatory fields of standard indicators: " + ", ".join(missing_mandatory_fields))

<<<<<<< HEAD
                        with col2:
                            if st.button("Delete", key=f"delete_modify_{grant_info_indx}_{grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}"):
                                delete_long_format_field(session, trustfund_id, fiscal_year_id)
                                st.success(f"Deleted Grant: {grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}")
                                st.rerun()
=======
                    with col2:
                        if st.button("Delete", key=f"delete_modify_{grant_info_indx}_{grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}"):
                            delete_long_format_field(session, trustfund_id, fiscal_year_id)
                            st.success(f"Deleted Grant: {grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}")
                            st.rerun()
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)

        else:
            st.write("No Grants found.")

    except Exception as e:
        st.error(f"An error occurred while managing Grants: {e}")

    finally:
        session.close()

# Helper functions for long format operations
def get_long_format_value(session, trustfund_id, fiscal_year_id, field_name, default_value=''):
    """
    Retrieve a specific field value from the long format table
    """
    try:
        result = session.query(GrantInfo).filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id,
            GrantInfo.field == field_name
        ).first()
        
        if result:
            return result.value if result.value is not None else default_value
        else:
            return default_value
    except Exception as e:
        st.error(f"Error retrieving {field_name}: {e}")
        return default_value


def update_long_format_field(session, trustfund_id, fiscal_year_id, field_name, field_value):
    """
    Update or insert a field value in the long format table
    """
    try:
        # Check if the record exists
        existing_record = session.query(GrantInfo).filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id,
            GrantInfo.field == field_name
        ).first()
        
        if existing_record:           
            # Update existing record
            existing_record.value = field_value
            existing_record.updated_at = datetime.datetime.now()
        else:
            # Create new record
            new_record = GrantInfo(
                trustfund_id=trustfund_id,
                fiscal_year_id=fiscal_year_id,
                field=field_name,
                value=field_value,
                team_id=current_team_id(),
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_record)
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        st.error(f"Error updating {field_name}: {e}")


def delete_long_format_field(session, trustfund_id, fiscal_year_id):
    try:
        # Assuming your model is named LongFormat and you have a session created
        # Adjust the model name according to your actual database model
        affected_rows = session.query(GrantInfo).filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id
        ).update({"deleted": True})

        # Commit the changes to the database
        session.commit()
        
    except Exception as e:
        session.rollback()  # Rollback in case of error
        print(f"Error occurred: {e}")


def get_long_format_dict(session, trustfund_id, fiscal_year_id, field_name, default_dict=None):
    """
    Retrieve a dictionary field from long format and safely evaluate it
    """
    if default_dict is None:
        default_dict = {}
    
    try:
        value_str = get_long_format_value(session, trustfund_id, fiscal_year_id, field_name, '{}')
        if value_str and value_str != '{}':
            return eval(value_str)
        else:
            return default_dict
    except Exception as e:
        st.error(f"Error parsing {field_name} dictionary: {e}")
        return default_dict


def new_grant():
    pass


def download_grants():
    # Set current_trustfund_id to None when focus lost from New grant reporting page
    st.session_state.current_trustfund_id = None
    st.session_state.current_fiscal_year_id = None
    
    session = create_session()
    team_id=current_team_id()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if st.button("Export Indicators", type="primary"):
        export_grants_indicator(
            session, f"Indicator_{timestamp}.csv", team_id=team_id, trustfund_id=current_trustfund_id())

    if st.button("Export Outputs/deliverables", type="primary"):
        export_grants_deliverable(
            session, f"Deliverable_{timestamp}.csv", team_id=team_id, trustfund_id=current_trustfund_id())


def read_data():
    # Function to fetch trustfunds from the database
    def fetch_trustfunds():
        session = create_session()
        try:
            # Query to select trustfunds
            trustfunds = session.query(TrustFund.id, TrustFund.name, TrustFund.grant).filter(
                TrustFund.project_type == 'Trust Fund', TrustFund.deleted == False, TrustFund.team_id == current_team_id(), TrustFund.name == current_username()).all()
            # Extract trustfunds from tuples
            return [(f"{trustfund[1]} - {trustfund[2]}", trustfund[0]) for trustfund in trustfunds]
        except Exception as e:
            print(f"Error fetching trustfunds: {e}")
            return []
        finally:
            session.close()

    # Fetch the trustfunds
    trustfunds = fetch_trustfunds()

    # Function to fetch countries from the database

    def fetch_countries():
        session = create_session()
        try:
            # Query to select countries
            countries = session.query(Country.id, Country.country).all()
            # Extract coutry from tuples
            return [(country[1], country[0]) for country in countries]
        except Exception as e:
            print(f"Error fetching pcodes: {e}")
            return []
        finally:
            session.close()  # Ensure the session is closed

    # Fetch the countries
    countries = fetch_countries()

    # Function to fetch regions from the database

    def fetch_regions():
        session = create_session()
        try:
            # Query to select regions
            regions = session.query(Region.id, Region.region).all()
            # Extract region from tuples
            return [(region[1], region[0]) for region in regions]
        except Exception as e:
            print(f"Error fetching regions: {e}")
            return []
        finally:
            session.close()

    # Fetch the regions
    regions = fetch_regions()

    # Function to fetch fiscalyears from the database

    def fetch_fiscalyears():
        session = create_session()
        try:
            # Query to select fiscalyears
            fys = session.query(FiscalYear.id, FiscalYear.fy).filter(
                FiscalYear.deleted == False).all()
            # Extract region from tuples
            return [(fy[1], fy[0]) for fy in fys]
        except Exception as e:
            print(f"Error fetching fiscal years: {e}")
            return []
        finally:
            session.close()

    # Fetch the fiscalyears
    fys = fetch_fiscalyears()

    # Return the fetched data as a dictionary (or tuple)
    return {
        "trustfunds": trustfunds,
        "countries": countries,
        "regions": regions,
        "fiscal_years": fys
    }


def export_grants_deliverable(session, filename, team_id, trustfund_id=None):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
<<<<<<< HEAD
        "deliverable_name", "deliverable_input_value", "deliverable_progress", "deliverable_description", "deliverable_data_source", "deliverable_next_steps", "deliverable_supporting_materials_url"
=======
        "deliverable_name", "deliverable_input_value", "deliverable_progress", "deliverable_quantity", "deliverable_description", "deliverable_data_source", "deliverable_next_steps", "deliverable_supporting_materials_url"
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
    ]

    # Fetch all records from the GrantInfo table in long format
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, 
        GrantInfo.deleted == False, 
        GrantInfo.trustfund_id==trustfund_id).all()

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
            if reconstructed_grant.trustfund_id:
                tf = session.query(TrustFund).filter_by(id=reconstructed_grant.trustfund_id, deleted=False).first()
                if tf:
                    trustfund_name = tf.name

            fiscal_year = ''
            if reconstructed_grant.fiscal_year_id:
                fy = session.query(FiscalYear).filter_by(id=reconstructed_grant.fiscal_year_id, deleted=False).first()
                if fy:
                    fiscal_year = fy.fy

            # Create a base row without deliverables
            base_row = {
                "trustfund": trustfund_name,
                "fiscal_year": fiscal_year,
                "country": country,
                "p_code_instrument": p_code_instrument,
                "p_code_description": p_code_description,
                "f4d_association": (
                    F4DAssociationEnum(f4d_association).value
                    if f4d_association is not None else None
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
                    "custom_name": indicator.indicator_name,
                } for indicator in indicators
            }

            # Handle deliverables dynamically
            if deliverables_dict:
                for key, value in deliverables_dict.items():
                    if key and isinstance(value, dict):
                        # Get standard and custom names from the mapping
                        indicator_info = indicator_name_map.get(
                            int(key), {"custom_name": ""})

                        deliverable_name = indicator_info["custom_name"]

                        # Access the nested value directly from `value`
                        deliverable_info = value

                        # Ensure deliverable_info is a dictionary
                        if isinstance(deliverable_info, dict):
                            # Create a new row for each deliverable
                            deliverable_row = base_row.copy()  # Copy the base row
                            deliverable_row["deliverable_name"] = deliverable_name
                            deliverable_row["deliverable_input_value"] = deliverable_info.get(
                                "input_value", "")
                            deliverable_row["deliverable_progress"] = deliverable_info.get(
                                "progress", "")
<<<<<<< HEAD
=======
                            deliverable_row["deliverable_quantity"] = deliverable_info.get(
                                "deliverable_quantity", "")
>>>>>>> e5c86a9 (Edit and Create merged and new text box added + extra On Hold option)
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
            else:
                # If no deliverables, add the base row
                csv_data.append(base_row)

        except Exception as e:
            print(f"Error processing grant info for trustfund_id {trustfund_id}, fiscal_year_id {fiscal_year_id}: {e}")


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


def export_grants_indicator(session, filename, team_id, trustfund_id=None):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "indicator_name", "indicator_input_value", "indicator_baseline_value", "indicator_year_baseline", "indicator_progress", "indicator_target_value", "indicator_year_target", "indicator_data_collection", "indicator_level_of_result"
    ]

    # Fetch all records from the GrantInfo table in long format
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, GrantInfo.deleted == False, GrantInfo.trustfund_id==trustfund_id).all()

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
            custom_indicators_dict = ast.literal_eval(custom_indicators_str) if custom_indicators_str and custom_indicators_str != '{}' else {}

            region_name = ''
            if region_id:
                region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                if region:
                    region_name = region.region

            trustfund_name = ''
            if reconstructed_grant.trustfund_id:
                tf = session.query(TrustFund).filter_by(id=reconstructed_grant.trustfund_id, deleted=False).first()
                if tf:
                    trustfund_name = tf.name

            fiscal_year = ''
            if reconstructed_grant.fiscal_year_id:
                fy = session.query(FiscalYear).filter_by(id=reconstructed_grant.fiscal_year_id, deleted=False).first()
                if fy:
                    fiscal_year = fy.fy

            # Create base row
            row = {
                "trustfund": trustfund_name,
                "fiscal_year": fiscal_year,
                "country": country,
                "region": region_name,
                "p_code_instrument": p_code_instrument,
                "p_code_description": p_code_description,
                "f4d_association": (
                    F4DAssociationEnum(f4d_association).value
                    if f4d_association is not None else None
                ),

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
                    "custom_name": indicator.indicator_name
                } for indicator in indicators
            }

            # Handle indicators dynamically
            if custom_indicators_dict:
                for key, value in custom_indicators_dict.items():
                    if key and isinstance(value, dict):
                        # Get standard and custom names from the mapping
                        indicator_info = indicator_name_map.get(
                            int(key), {"custom_name": ""})
                        custom_indicator_name = indicator_info["custom_name"]


                        # Access the nested value directly from `value`
                        indicator_info = value
                        # Ensure indicator_info is a dictionary
                        if isinstance(indicator_info, dict):
                            # Create a new row for each indicator
                            indicator_row = row.copy()  # Copy the base row
                            indicator_row["indicator_name"] = custom_indicator_name
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
            else:
                # If no indicators, add the base row
                csv_data.append(row)

        except Exception as e:
            print(f"Error processing grant info for trustfund_id {trustfund_id}, fiscal_year_id {fiscal_year_id}: {e}")


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


if __name__ == "__main__":
    main()
