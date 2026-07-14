# Auto-split from the original monolithic main.py. See git history.
import ast
import datetime
import uuid
import pandas as pd
import streamlit as st
from connection import create_session
from model import (
    GrantInfo, TrustFund, Indicator, TrustFundIndicatorMapping,
)
from f4d.context import (
    current_team_id, current_username,
)
from f4d.data_access import set_blob_entry_archived
from f4d.reporting_export import export_report_safe


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

    # Archived admin-mapped indicators — collected here and shown (with a
    # Restore option) in the archived section below instead of as form rows.
    archived_mapped = []

    # Iterate through each mapping and display appropriate input fields
    for mapping in mappings:
        indicator = session.query(Indicator).filter(
            Indicator.id == mapping.indicator_id, Indicator.custom_indicator == True).first()

        if indicator:
            # Skip archived indicators — they move to the archived section and
            # are excluded from the form and from mandatory-field validation.
            if custom_indicators_data.get(str(mapping.indicator_id), {}).get("archived"):
                archived_mapped.append((str(mapping.indicator_id), indicator.indicator_name))
                continue

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
                # Progress Value is intentionally NOT carried forward: each fiscal
                # year the TTL must enter fresh progress. The prior year's value is
                # still shown (read-only) via show_previous_fiscal_year_indicators().

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

                st.markdown(f"**Unit of measure:** {indicator.unit_of_measurement or 'Not specified'}")

                # Display input fields based on unit_of_measurement
                if indicator.unit_of_measurement == 'Date':
                    input_value = st.date_input(
                        f"Progress Value: {indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"date_input_{mapping.id}")
                elif indicator.unit_of_measurement == 'Number' or indicator.unit_of_measurement == 'Percentage':
                    input_value = st.number_input(
                        f"Progress Value: {indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"number_input_{mapping.id}")
                elif indicator.unit_of_measurement == 'Short Text':
                    input_value = st.text_input(
                        f"Progress Value: {indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"short_text_input_{mapping.id}", placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
                elif indicator.unit_of_measurement == 'Long Text':
                    input_value = st.text_area(
                        f"Progress Value: {indicator.indicator_prompt} {mandatory_char}", value=input_value,  key=f"long_text_input_{mapping.id}", placeholder=f"{indicator.indicator_definition if indicator.indicator_definition else ''}")
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
                        f"Progress Value: {indicator.indicator_prompt} {mandatory_char}", categories, index=categories.index(input_value) if input_value in categories else None, key=f"categorical_input_{mapping.id}"
                    )
                else:
                    st.write("No valid unit of measurement provided.")
                    continue

                progress = st.text_area(
                    "Explain the Progress",
                    value=progress,
                    key=f"progress_{mapping.id}"
                )

                baseline_value = st.text_input(
                    "Baseline value", value=baseline_value,
                    key=f"baseline_value_{mapping.id}"
                )

                year_baseline = st.number_input(
                    "Year baseline data was collected", value=year_baseline, min_value=1900, max_value=2100,
                    key=f"year_baseline_{mapping.id}"
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

                # Drop this indicator (soft-delete/archive, persisted immediately).
                _m_confirm = f"ci_confirm_archive_map_{mapping.indicator_id}"
                if st.session_state.get(_m_confirm):
                    st.warning("Drop this indicator? It will be hidden but not "
                               "permanently deleted. Unsaved edits above won't be kept.")
                    _reason_key = f"ci_drop_reason_map_{mapping.indicator_id}"
                    drop_reason = st.text_input(
                        "Reason for dropping (optional)", key=_reason_key)
                    a1, a2 = st.columns(2)
                    if a1.button("Confirm drop", key=f"ci_do_archive_map_{mapping.indicator_id}", type="primary"):
                        set_blob_entry_archived(
                            session, trustfund_id, st.session_state.current_fiscal_year_id,
                            "custom_indicators", str(mapping.indicator_id), True, reason=drop_reason)
                        st.session_state.pop(_m_confirm, None)
                        st.session_state.pop(_reason_key, None)
                        st.rerun()
                    if a2.button("Cancel", key=f"ci_cancel_archive_map_{mapping.indicator_id}"):
                        st.session_state.pop(_m_confirm, None)
                        st.rerun()
                else:
                    if st.button("Drop this Results Indicator", key=f"ci_archive_map_{mapping.indicator_id}"):
                        st.session_state[_m_confirm] = True
                        st.rerun()

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


    # ---- User-added (custom) results indicators ---------------------------
    # TTLs can add their own indicators beyond the admin-mapped ones. These
    # live in the same custom_indicators blob under "custom_*" keys with a
    # human-entered name and a "custom" flag. Soft-deleted entries are kept
    # with "archived": True so they can be restored/audited.
    _LEVELS = ["Outcome", "Intermediate Outcome", "Output"]
    _UNIT_OPTIONS = ["Number", "Percentage", "Short Text", "Long Text", "Date", "Categorical"]
    st.session_state.setdefault("pending_custom_indicators", {})
    # Seed any just-added (unsaved) custom entries so they render until saved.
    for ckey, cname in st.session_state.pending_custom_indicators.items():
        if ckey not in custom_indicators_data:
            custom_indicators_data[ckey] = {
                "name": cname, "custom": True, "archived": False,
                "level_of_result": None, "unit": "", "input_value": "", "baseline_value": "",
                "year_baseline": None, "progress": "", "target_value": "",
                "year_target": None, "data_collection": "",
            }

    ci_custom_keys = [k for k, v in custom_indicators_data.items()
                      if isinstance(v, dict) and v.get("custom")]
    ci_active = [k for k in ci_custom_keys if not custom_indicators_data[k].get("archived")]
    ci_archived = [k for k in ci_custom_keys if custom_indicators_data[k].get("archived")]

    if ci_active:
        st.markdown("#### Your added indicators")
    for ckey in ci_active:
        entry = custom_indicators_data[ckey]
        with st.expander(entry.get("name") or "Untitled indicator"):
            _lvl = entry.get("level_of_result")
            entry["level_of_result"] = st.selectbox(
                "Level of result", _LEVELS,
                index=_LEVELS.index(_lvl) if _lvl in _LEVELS else None,
                key=f"ci_custom_level_{ckey}")
            _unit = entry.get("unit")
            entry["unit"] = st.selectbox(
                "Unit of measure", _UNIT_OPTIONS,
                index=_UNIT_OPTIONS.index(_unit) if _unit in _UNIT_OPTIONS else None,
                key=f"ci_custom_unit_{ckey}",
                help="What kind of value should be entered for this indicator's Progress Value?")
            entry["input_value"] = st.text_area(
                "Progress Value", value=entry.get("input_value", ""),
                key=f"ci_custom_input_{ckey}")
            entry["progress"] = st.text_area(
                "Explain the Progress", value=entry.get("progress", ""),
                key=f"ci_custom_progress_{ckey}")
            entry["baseline_value"] = st.text_input(
                "Baseline value", value=entry.get("baseline_value", ""),
                key=f"ci_custom_baseline_{ckey}")
            entry["year_baseline"] = st.number_input(
                "Year baseline data was collected",
                value=entry.get("year_baseline") or None,
                min_value=1900, max_value=2100, key=f"ci_custom_ybase_{ckey}")
            entry["target_value"] = st.text_input(
                "Target value", value=entry.get("target_value", ""),
                key=f"ci_custom_target_{ckey}")
            entry["year_target"] = st.number_input(
                "Year target data will be collected",
                value=entry.get("year_target") or None,
                min_value=1900, max_value=2100, key=f"ci_custom_ytarget_{ckey}")
            entry["data_collection"] = st.text_area(
                "How are you collecting the data?",
                value=entry.get("data_collection", ""),
                key=f"ci_custom_datacol_{ckey}")

            # Drop with a confirm step (archived, not permanently removed).
            confirm_key = f"ci_confirm_remove_{ckey}"
            if st.session_state.get(confirm_key):
                st.warning("Drop this indicator? It will be archived, not permanently deleted.")
                _creason_key = f"ci_drop_reason_{ckey}"
                drop_reason = st.text_input(
                    "Reason for dropping (optional)", key=_creason_key)
                c1, c2 = st.columns(2)
                if c1.button("Confirm drop", key=f"ci_do_remove_{ckey}", type="primary"):
                    # Drop unsaved drafts from pending; persist saved ones now so
                    # the archived flag survives the per-rerun blob reload.
                    st.session_state.pending_custom_indicators.pop(ckey, None)
                    set_blob_entry_archived(
                        session, trustfund_id, st.session_state.current_fiscal_year_id,
                        "custom_indicators", ckey, True, create_if_missing=False, reason=drop_reason)
                    st.session_state.pop(confirm_key, None)
                    st.session_state.pop(_creason_key, None)
                    st.rerun()
                if c2.button("Cancel", key=f"ci_cancel_remove_{ckey}"):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
            else:
                if st.button("Drop this Results Indicator", key=f"ci_remove_{ckey}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

    # Add-an-indicator control.
    with st.expander("➕ Add an indicator"):
        new_name = st.text_input("Indicator name", key="new_custom_indicator_name")
        if st.button("Add indicator", key="add_custom_indicator"):
            if new_name and new_name.strip():
                new_key = f"custom_{uuid.uuid4().hex[:8]}"
                st.session_state.pending_custom_indicators[new_key] = new_name.strip()
                st.session_state.pop("new_custom_indicator_name", None)
                st.rerun()
            else:
                st.warning("Please enter a name for the new indicator.")

    # Archived indicators — restore option (both custom and admin-mapped).
    if ci_archived or archived_mapped:
        with st.expander("🗄️ Archived indicators"):
            for ckey in ci_archived:
                entry = custom_indicators_data[ckey]
                cols = st.columns([4, 1])
                cols[0].write(entry.get("name") or "Untitled indicator")
                if cols[1].button("Restore", key=f"ci_restore_{ckey}"):
                    set_blob_entry_archived(
                        session, trustfund_id, st.session_state.current_fiscal_year_id,
                        "custom_indicators", ckey, False, create_if_missing=False)
                    st.rerun()
            for mkey, mname in archived_mapped:
                cols = st.columns([4, 1])
                cols[0].write(mname)
                if cols[1].button("Restore", key=f"ci_restore_map_{mkey}"):
                    set_blob_entry_archived(
                        session, trustfund_id, st.session_state.current_fiscal_year_id,
                        "custom_indicators", mkey, False, create_if_missing=False)
                    st.rerun()

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
                    export_report_safe()  # refresh the master export in the background
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

