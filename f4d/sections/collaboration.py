# Auto-split from the original monolithic main.py. See git history.
import datetime
import streamlit as st
from connection import create_session
from model import (
    GrantInfo,
)
from f4d.context import (
    current_team_id,
)


def collaboration_partnership():
    st.success("### 4. Collaboration/Partnership")

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

    # Clear widget keys whenever the fiscal year changes so fields reload from DB
    _COLLAB_KEYS = [
        "collaborations_input", "other_teams_input", "other_ifis_input",
        "other_orgs_input", "describe_collaboration_input", "lessons_learned_input",
    ]
    if st.session_state.get("collab_loaded_for_fy") != st.session_state.current_fiscal_year_id:
        for _k in _COLLAB_KEYS:
            st.session_state.pop(_k, None)
        st.session_state.pop("collaboration_initial_values", None)
        st.session_state["collab_loaded_for_fy"] = st.session_state.current_fiscal_year_id

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

