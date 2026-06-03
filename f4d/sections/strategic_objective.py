# Auto-split from the original monolithic main.py. See git history.
import datetime
import streamlit as st
from connection import create_session
from model import (
    GrantInfo,
)
from f4d.context import (
    normalize, current_team_id,
)


def strategic_objective_progress():
    st.success("### 2. Strategic Objective & Progress")

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

    # Clear widget keys whenever the fiscal year changes so fields reload from DB
    _STRAT_KEYS = [
        "strat_challenges", "strat_strategic_objective", "strat_overall_progress",
        "strat_implementation_challenges", "strat_public_communication_external",
        "strat_public_communication_internal",
    ]
    if st.session_state.get("strat_loaded_for_fy") != st.session_state.current_fiscal_year_id:
        for _k in _STRAT_KEYS:
            st.session_state.pop(_k, None)
        st.session_state.pop("strategic_objective_initial_values", None)
        st.session_state["strat_loaded_for_fy"] = st.session_state.current_fiscal_year_id

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
        placeholder="What is the key challenge(s) the client country faces that this grant intends to address?",
        key="strat_challenges"
    )
    strategic_objective = st.text_area(
        "Grant's strategic objective (Max 200 words) *",
        value=strategic_objective,
        placeholder="What the grant is expected to achieve to address the challenges. Max. 200 words.",
        key="strat_strategic_objective"
    )
    overall_progress = st.text_area(
        "Overall progress since inception *",
        value=overall_progress,
        placeholder="Please provide a short summary of the overall progress since inception of the grant towards achieving the strategic objective, with a focus on progress towards outcomes instead of listing deliverables. Include details including developments in client support/interest, coordination and partnerships with other donors, development partners and/or other WB units and IFC; include any relevant lessons learned.",
        key="strat_overall_progress"
    )
    implementation_challenges = st.text_area(
        "Implementation Challenges",
        value=implementation_challenges,
        placeholder="Please provide any challenges faced so far, any external or unexpected events that affect the implementation or results.",
        key="strat_implementation_challenges"
    )
    public_communication_external = st.text_area(
        "Public communication (external)",
        value=public_communication_external,
        placeholder="List external public communications that took place. Examples include a link to a press release, an external conference, counterpart quotes, newspaper, journals, articles, blogs, website, data infographics, brochures, booklet, reports, TV, YouTube video, photos, etc. Send attachments to financefordevelopment@worldbank.org if there is no link.",
        key="strat_public_communication_external"
    )
    public_communication_internal = st.text_area(
        "Public communication (internal)",
        value=public_communication_internal,
        placeholder="List any World Bank intranet appearances (such as links to blog posts, feature stories, Up Front story, photos of internal events, data infographics, etc.). Send attachments to financefordevelopment@worldbank.org if there is no link.",
        key="strat_public_communication_internal"
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

