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
        "Target Number of Deliverables": progress_status
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

    # Archived admin-mapped deliverables — collected here and shown (with a
    # Restore option) in the archived section below instead of as form rows.
    archived_mapped = []

    # Iterate through each mapping and display appropriate input fields
    for mapping in mappings:
        indicator = session.query(Indicator).filter(
            Indicator.id == mapping.indicator_id, Indicator.custom_indicator == False).first()

        if indicator:
            # Skip archived deliverables — they move to the archived section and
            # are excluded from the form and from mandatory-field validation.
            if deliverables_data.get(str(mapping.indicator_id), {}).get("archived"):
                archived_mapped.append((str(mapping.indicator_id), indicator.indicator_name))
                continue

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
                    "Target Number of Deliverables",
                    placeholder="e.g. 3",
                    help="How many subparts does this deliverable have? "
                         "(e.g. 2 datasets and a web portal. Input: 3.)",
                    value=progress,
                    key=f"progress_{mapping.id}",
                )

                deliverable_quantity = st.text_input(
                    "Number of Deliverables In Progress or Completed",
                    placeholder="e.g. 2",
                    help="How many of the deliverables have been completed "
                         "(e.g. 2 of 5 completed. Input: 2).",
                    value=deliverable_quantity,
                    key=f"deliverable_quantity_{mapping.id}",
                )

                next_steps = st.text_area(
                    "Next steps and any required adjustments next FY",
                    value=next_steps,
                    placeholder="Describe any adjustments to the deliverable(s) that will be required going forward.",
                    key=f"next_steps_{mapping.id}",
                )

                _media_opts = ["No", "Yes"]
                supporting_materials_url = st.radio(
                    "Do you have any photos, videos, articles, or related items "
                    "that you can share related to the deliverables?",
                    _media_opts,
                    index=_media_opts.index(supporting_materials_url) if supporting_materials_url in _media_opts else 0,
                    horizontal=True,
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

                # Drop this deliverable (soft-delete/archive, persisted immediately).
                _m_confirm = f"confirm_archive_map_{mapping.indicator_id}"
                if st.session_state.get(_m_confirm):
                    st.warning("Drop this deliverable? It will be hidden but not "
                               "permanently deleted. Unsaved edits above won't be kept.")
                    _reason_key = f"drop_reason_map_{mapping.indicator_id}"
                    drop_reason = st.text_input(
                        "Reason for dropping (optional)", key=_reason_key)
                    a1, a2 = st.columns(2)
                    if a1.button("Confirm drop", key=f"do_archive_map_{mapping.indicator_id}", type="primary"):
                        set_blob_entry_archived(
                            session, trustfund_id, st.session_state.current_fiscal_year_id,
                            "deliverables", str(mapping.indicator_id), True, reason=drop_reason)
                        st.session_state.pop(_m_confirm, None)
                        st.session_state.pop(_reason_key, None)
                        st.rerun()
                    if a2.button("Cancel", key=f"cancel_archive_map_{mapping.indicator_id}"):
                        st.session_state.pop(_m_confirm, None)
                        st.rerun()
                else:
                    if st.button("Drop this Deliverable", key=f"archive_map_{mapping.indicator_id}"):
                        st.session_state[_m_confirm] = True
                        st.rerun()

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
    

    # ---- User-added (custom) deliverables ---------------------------------
    # TTLs can add their own deliverables beyond the admin-mapped indicators.
    # These live in the same deliverables_data blob under "custom_*" keys and
    # carry a human-entered name plus a "custom" flag. Soft-deleted entries are
    # kept with "archived": True so they can be restored/audited.
    st.session_state.setdefault("pending_custom_deliverables", {})
    # Seed any just-added (unsaved) custom entries so they render until saved.
    for ckey, cname in st.session_state.pending_custom_deliverables.items():
        if ckey not in deliverables_data:
            deliverables_data[ckey] = {
                "name": cname, "custom": True, "archived": False,
                "input_value": "", "progress": "", "deliverable_quantity": "",
                "description": "", "data_source": "", "next_steps": "",
                "supporting_materials_url": "",
            }

    custom_keys = [k for k, v in deliverables_data.items()
                   if isinstance(v, dict) and v.get("custom")]
    active_custom = [k for k in custom_keys if not deliverables_data[k].get("archived")]
    archived_custom = [k for k in custom_keys if deliverables_data[k].get("archived")]

    if active_custom:
        st.markdown("#### Your added deliverables")
    for ckey in active_custom:
        entry = deliverables_data[ckey]
        with st.expander(entry.get("name") or "Untitled deliverable"):
            entry["input_value"] = st.text_area(
                "Deliverable", value=entry.get("input_value", ""),
                key=f"custom_input_{ckey}")
            entry["progress"] = st.text_input(
                "Target Number of Deliverables", value=entry.get("progress", ""),
                placeholder="e.g. 3",
                help="How many subparts does this deliverable have? "
                     "(e.g. 2 datasets and a web portal. Input: 3.)",
                key=f"custom_progress_{ckey}")
            entry["deliverable_quantity"] = st.text_input(
                "Number of Deliverables In Progress or Completed",
                value=entry.get("deliverable_quantity", ""),
                placeholder="e.g. 2",
                help="How many of the deliverables have been completed "
                     "(e.g. 2 of 5 completed. Input: 2).",
                key=f"custom_qty_{ckey}")
            entry["next_steps"] = st.text_area(
                "Next steps and any required adjustments next FY",
                value=entry.get("next_steps", ""), key=f"custom_next_{ckey}")
            _media_opts_c = ["No", "Yes"]
            _media_cur = entry.get("supporting_materials_url", "")
            entry["supporting_materials_url"] = st.radio(
                "Do you have any photos, videos, articles, or related items "
                "that you can share related to the deliverables?",
                _media_opts_c,
                index=_media_opts_c.index(_media_cur) if _media_cur in _media_opts_c else 0,
                horizontal=True,
                key=f"custom_url_{ckey}")
            entry["description"] = st.text_area(
                "Brief description of the deliverable(s), including risk of delay",
                value=entry.get("description", ""), key=f"custom_desc_{ckey}")
            entry["data_source"] = st.text_input(
                "Data source", value=entry.get("data_source", ""),
                key=f"custom_source_{ckey}")

            # Drop with a confirm step (archived, not permanently removed).
            confirm_key = f"confirm_remove_{ckey}"
            if st.session_state.get(confirm_key):
                st.warning("Drop this deliverable? It will be archived, not permanently deleted.")
                _creason_key = f"drop_reason_{ckey}"
                drop_reason = st.text_input(
                    "Reason for dropping (optional)", key=_creason_key)
                c1, c2 = st.columns(2)
                if c1.button("Confirm drop", key=f"do_remove_{ckey}", type="primary"):
                    # Drop unsaved drafts from pending; persist saved ones now so
                    # the archived flag survives the per-rerun blob reload.
                    st.session_state.pending_custom_deliverables.pop(ckey, None)
                    set_blob_entry_archived(
                        session, trustfund_id, st.session_state.current_fiscal_year_id,
                        "deliverables", ckey, True, create_if_missing=False, reason=drop_reason)
                    st.session_state.pop(confirm_key, None)
                    st.session_state.pop(_creason_key, None)
                    st.rerun()
                if c2.button("Cancel", key=f"cancel_remove_{ckey}"):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
            else:
                if st.button("Drop this Deliverable", key=f"remove_{ckey}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

    # Add-a-deliverable control.
    with st.expander("➕ Add a deliverable"):
        new_name = st.text_input("Deliverable name", key="new_custom_deliverable_name")
        if st.button("Add deliverable", key="add_custom_deliverable"):
            if new_name and new_name.strip():
                new_key = f"custom_{uuid.uuid4().hex[:8]}"
                st.session_state.pending_custom_deliverables[new_key] = new_name.strip()
                st.session_state.pop("new_custom_deliverable_name", None)
                st.rerun()
            else:
                st.warning("Please enter a name for the new deliverable.")

    # Archived deliverables — restore option (both custom and admin-mapped).
    if archived_custom or archived_mapped:
        with st.expander("🗄️ Archived deliverables"):
            for ckey in archived_custom:
                entry = deliverables_data[ckey]
                cols = st.columns([4, 1])
                cols[0].write(entry.get("name") or "Untitled deliverable")
                if cols[1].button("Restore", key=f"restore_{ckey}"):
                    set_blob_entry_archived(
                        session, trustfund_id, st.session_state.current_fiscal_year_id,
                        "deliverables", ckey, False, create_if_missing=False)
                    st.rerun()
            for mkey, mname in archived_mapped:
                cols = st.columns([4, 1])
                cols[0].write(mname)
                if cols[1].button("Restore", key=f"restore_map_{mkey}"):
                    set_blob_entry_archived(
                        session, trustfund_id, st.session_state.current_fiscal_year_id,
                        "deliverables", mkey, False, create_if_missing=False)
                    st.rerun()

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

    save_clicked = st.button("Save", key="save_deliverable", type="primary")

    if save_clicked:
        if deliverables_data:
            if existing_grant_info:
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
                export_report_safe()  # refresh the master export in the background
                # Save always persists; missing mandatory fields are surfaced as
                # a non-blocking note (the separate "Save draft" button is gone).
                if missing_mandatory_fields:
                    st.warning("Saved. Still incomplete: " +
                               ", ".join(missing_mandatory_fields))
                else:
                    st.success("Outputs/deliverables saved successfully!")

                # Reset change tracking after save
                st.session_state.deliverables_unsaved_changes = False
                st.session_state.deliverables_initial_values = current_values
            else:
                st.warning(
                    "No Grant Info exists! Please create one in Basic Grant Information subpage")
        else:
            st.error("No deliverables were captured.")

        
    # Display a warning if there are unsaved changes
    if st.session_state.deliverables_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    session.close()
            

