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
from f4d.exports import read_data


def lending_operations():
    st.success("### 3. Operations Informed and Country Engagements Informed by F4D")

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

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

