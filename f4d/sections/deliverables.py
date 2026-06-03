# Auto-split from the original monolithic main.py. See git history.
import ast
import datetime
import pandas as pd
import streamlit as st
from connection import create_session
from model import (
    GrantInfo, TrustFund, Indicator, TrustFundIndicatorMapping,
)
from f4d.context import (
    current_team_id, current_username,
)


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

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

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
                        "deliverable_quantity": deliverables_data.get(str(mapping.indicator_id), {}).get("deliverable_quantity", ""),
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
            deliverable_quantity = deliverables_data.get(str(mapping.indicator_id), {}).get("deliverable_quantity", "")
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
                "deliverable_quantity": deliverable_quantity,
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
                        f"{indicator.indicator_prompt} {mandatory_char}",
                        categories,
                        index=categories.index(input_value) if input_value in categories else None,
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

                deliverable_quantity = st.text_input(
                    "Deliverable quantity",
                    placeholder="Enter the number or quantity of this deliverable (e.g., number of MSMEs informed, number of reports produced).",
                    value=deliverable_quantity,
                    key=f"deliverable_quantity_{mapping.id}",
                )

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
                    "deliverable_quantity": deliverable_quantity,
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
                    "deliverable_quantity": deliverable_quantity,
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
            

