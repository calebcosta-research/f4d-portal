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

    if not st.session_state.current_fiscal_year_id:
        st.warning("Please go to **Basic Grant Information** and select a fiscal year first.")
        return

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

