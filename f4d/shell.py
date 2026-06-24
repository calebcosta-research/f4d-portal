# Auto-split from the original monolithic main.py. See git history.
import streamlit as st
from connection import create_session
from model import (
    GrantInfo, TrustFund,
)
from f4d.context import (
    _resolve_grant_context, current_team_id,
    current_username, current_grantname,
)
from f4d.auth import display_login_form
from f4d.sections.home import home
from f4d.sections.basic_grant_info import basic_grant_info
from f4d.sections.strategic_objective import strategic_objective_progress
from f4d.sections.lending_operations import lending_operations
from f4d.sections.collaboration import collaboration_partnership
from f4d.sections.deliverables import deliverables
from f4d.sections.custom_indicators import custom_indicators
from f4d.sections.review_submit import review_submit


def main():
    # Hide Streamlit's "Press Ctrl+Enter to apply" hint, which overlapped
    # typed text in text areas/inputs (reported on Strategic Objectives).
    st.markdown(
        '<style>[data-testid="InputInstructions"]{display:none;}</style>',
        unsafe_allow_html=True,
    )

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


def _show_report_mode_banner():
    """Show a banner indicating whether the TTL is creating or editing their report."""
    session = create_session()
    try:
        trustfund = session.query(TrustFund).filter(
            TrustFund.name == current_username(),
            TrustFund.team_id == current_team_id()
        ).first()
        if not trustfund:
            return
        existing = session.query(GrantInfo).filter_by(
            trustfund_id=trustfund.id,
            deleted=False
        ).first()
        if existing:
            fy = existing.fiscal_year.fy if existing.fiscal_year else ""
            st.info(f"✏️ Editing existing report — {fy}")
        else:
            st.info("➕ Creating new report")
    except Exception:
        pass
    finally:
        session.close()


def display_main_app():
    # Define pages with subpages
    pages = {
          "Home": [home, None],
          "Report new results": [new_grant, None],
    }
    
    # Map subpages for specific main pages
    subpages = {
        "Report new results": [
            "Basic Grant Information", 
            "Strategic Objective & Progress", 
            "Lending Operations", 
            "Collaboration/Partnership", 
            "Outputs/deliverables",
            "Results Indicators",
            "Review & Submit"
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

    # Widget keys to wipe per section when the user chooses "Leave without saving"
    section_discard_keys = {
        "Basic Grant Information": [
            "bgi_fiscal_year", "bgi_p_code_instrument", "bgi_p_code_description",
            "bgi_f4d_association", "bgi_region", "bgi_country", "bgi_pillars", "bgi_ccts",
            "Pillar 1: Strengthening Financial Sector Resiliency",
            "Pillar 2: Financing the Poor and Vulnerable",
            "Pillar 3: Financing the Real Economy",
            "Pillar 4: Developing Financial Markets",
            "Climate change and sustainable finance",
            "Advancing digitalization",
            "Financing solutions to close gender gaps",
            "bgi_loaded_for_fy", "grant_info_initial_values",
        ],
        "Strategic Objective & Progress": [
            "strat_challenges", "strat_strategic_objective", "strat_overall_progress",
            "strat_implementation_challenges", "strat_public_communication_external",
            "strat_public_communication_internal",
            "strat_loaded_for_fy", "strategic_objective_initial_values",
        ],
        "Lending Operations": [
            "operation_list", "cpfs_list",
            "operations_unsaved_changes", "operations_initial_values",
        ],
        "Collaboration/Partnership": [
            "collaborations_input", "other_teams_input", "other_ifis_input",
            "other_orgs_input", "describe_collaboration_input", "lessons_learned_input",
            "collab_loaded_for_fy", "collaboration_initial_values",
        ],
        "Outputs/deliverables": ["_deliverables_discard"],
        "Results Indicators": ["_indicators_discard"],
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
        # Clear unsaved changes flag and discard widget state for the section being left
        if st.session_state.current_main_page == "Report new results" and st.session_state.current_subpage in unsaved_mapping:
            st.session_state[unsaved_mapping[st.session_state.current_subpage]] = False
            for _k in section_discard_keys.get(st.session_state.current_subpage, []):
                st.session_state.pop(_k, None)
            # Deliverables / Results Indicators use dynamic keys — clear by prefix
            _DELIVERABLE_PREFIXES = (
                "date_input_", "number_input_", "short_text_input_", "long_text_input_",
                "percentage_input_", "categorical_input_",
                "progress_", "deliverable_quantity_", "next_steps_",
                "supporting_materials_url_", "description_", "data_source_",
            )
            _INDICATOR_PREFIXES = (
                "level_of_result_",
                "date_input_", "number_input_", "short_text_input_", "long_text_input_",
                "percentage_input_", "categorical_input_",
                "baseline_value_", "year_baseline_", "progress_",
                "target_value_", "year_target_", "data_collection_",
            )
            if st.session_state.current_subpage == "Outputs/deliverables":
                for _k in list(st.session_state.keys()):
                    if any(_k.startswith(p) for p in _DELIVERABLE_PREFIXES):
                        del st.session_state[_k]
            elif st.session_state.current_subpage == "Results Indicators":
                for _k in list(st.session_state.keys()):
                    if any(_k.startswith(p) for p in _INDICATOR_PREFIXES):
                        del st.session_state[_k]
        
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
        _show_report_mode_banner()
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
        elif current_sub == "Review & Submit":
            review_submit()
        else:
            basic_grant_info()
    else:
        st.error(f"Page '{current_main}' not found")


def new_grant():
    pass

