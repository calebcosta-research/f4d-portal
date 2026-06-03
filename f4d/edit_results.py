# Auto-split from the original monolithic main.py. See git history.
import ast
import datetime
import streamlit as st
from connection import create_session
from model import (
    F4DAssociationEnum, GrantInfo, TrustFund, Indicator, TrustFundIndicatorMapping,
    User,
)
from f4d.data_access import (
    get_long_format_value, update_long_format_field,
    delete_long_format_field,
)
from f4d.exports import read_data


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
                    _sec_tabs = st.tabs([
                        "1. Basic Grant Information",
                        "2. Strategic Objective & Progress",
                        "3. Lending Operations",
                        "4. Collaboration/Partnership",
                        "5. Outputs/Deliverables",
                        "6. Results Indicators",
                    ])
                    with _sec_tabs[0]:
                        
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

                    with _sec_tabs[1]:

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

                    with _sec_tabs[2]:
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

                    with _sec_tabs[3]:

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

                    with _sec_tabs[4]:

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
                                    deliverable_quantity = existing_data.get("deliverable_quantity", "")
                                    description = existing_data.get("description")
                                    data_source = existing_data.get("data_source")
                                    next_steps = existing_data.get("next_steps")
                                    supporting_materials_url = existing_data.get("supporting_materials_url")
                                else:
                                    input_value = None
                                    progress = ""
                                    deliverable_quantity = ""
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
                                        f"{j} - {indicator.indicator_prompt} {mandatory_char}",
                                        categories,
                                        index=categories.index(input_value) if input_value in categories else None,
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

                                deliverable_quantity = st.text_input(
                                    f"{j} - Deliverable quantity",
                                    placeholder="Enter the number or quantity of this deliverable (e.g., number of MSMEs informed, number of reports produced).",
                                    value=deliverable_quantity,
                                    key=f"deliverable_quantity_{grant_info_indx}_{mapping.id}"
                                )

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
                                    "deliverable_quantity": deliverable_quantity,
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

                    with _sec_tabs[5]:

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

                    # Update/Delete buttons appear below tabs, accessible from any section
                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button("Update", key=f"update_{grant_info_indx}_{grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}"):
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

                    with col2:
                        if st.button("Delete", key=f"delete_modify_{grant_info_indx}_{grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}"):
                            delete_long_format_field(session, trustfund_id, fiscal_year_id)
                            st.success(f"Deleted Grant: {grant_info.trustfund.name}_{grant_info.fiscal_year.fy if grant_info.fiscal_year else ''}")
                            st.rerun()

        else:
            st.write("No Grants found.")

    except Exception as e:
        st.error(f"An error occurred while managing Grants: {e}")

    finally:
        session.close()

# Helper functions for long format operations

