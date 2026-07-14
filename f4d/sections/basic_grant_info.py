# Auto-split from the original monolithic main.py. See git history.
import ast
import datetime
import streamlit as st
from connection import create_session
from model import (
    F4DAssociationEnum, GrantInfo,
)
from f4d.context import (
    current_team_id, current_trustfund_id,
)
from f4d.exports import read_data


def basic_grant_info():
    st.success("### 1. Basic Grant Information")
    data = read_data()

    session = create_session()

    print(st.session_state.current_trustfund_id, st.session_state.current_fiscal_year_id)

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

    _NEW_LABEL = "➕ New fiscal year report"

    # Show the FY switcher whenever at least one saved year exists so the user
    # can both switch between existing years and start a new one.
    if len(saved_fy_options) >= 1:
        switcher_labels = [_NEW_LABEL] + [opt[0] for opt in saved_fy_options]
        creating_new = st.session_state.get("bgi_creating_new", False)

        if creating_new or st.session_state.current_fiscal_year_id is None:
            current_switcher_index = 0  # "➕ New fiscal year report"
        else:
            current_switcher_index = next(
                (i + 1 for i, opt in enumerate(saved_fy_options)
                 if opt[1] == st.session_state.current_fiscal_year_id),
                1  # default to the first saved FY if not found
            )

        def _on_fy_switch():
            selected = st.session_state["_fy_switcher"]
            if selected == _NEW_LABEL:
                st.session_state.bgi_creating_new = True
                st.session_state.current_fiscal_year_id = None
            else:
                st.session_state.bgi_creating_new = False
                st.session_state.current_fiscal_year_id = next(
                    (opt[1] for opt in saved_fy_options if opt[0] == selected), None
                )
            st.session_state.pop("grant_info_initial_values", None)

        st.selectbox(
            "Existing report(s):",
            switcher_labels,
            index=current_switcher_index,
            key="_fy_switcher",
            on_change=_on_fy_switch,
        )
    elif len(saved_fy_options) == 0:
        # No saved data yet — new user, form will be blank
        st.session_state.bgi_creating_new = False
    else:
        # Exactly one saved FY and no switcher shown — auto-select it
        if st.session_state.current_fiscal_year_id is None:
            st.session_state.current_fiscal_year_id = saved_fy_options[0][1]

    # Clear all form widget keys whenever the fiscal year changes so fields reload from DB
    _BGI_WIDGET_KEYS = [
        "bgi_fiscal_year", "bgi_p_code_instrument", "bgi_p_code_description",
        "bgi_f4d_association", "bgi_region", "bgi_country", "bgi_pillars", "bgi_ccts",
        "Pillar 1: Strengthening Financial Sector Resiliency",
        "Pillar 2: Financing the Poor and Vulnerable",
        "Pillar 3: Financing the Real Economy",
        "Pillar 4: Developing Financial Markets",
        "Climate change and sustainable finance",
        "Advancing digitalization",
        "Financing solutions to close gender gaps",
    ]
    # Use a sentinel so "creating new" (fy_id=None) is treated as its own stable state
    _loaded_key = ("new" if st.session_state.get("bgi_creating_new") else st.session_state.current_fiscal_year_id)
    if st.session_state.get("bgi_loaded_for_fy") != _loaded_key:
        for _k in _BGI_WIDGET_KEYS:
            st.session_state.pop(_k, None)
        st.session_state.pop("grant_info_initial_values", None)
        st.session_state["bgi_loaded_for_fy"] = _loaded_key

    # Load the existing record for the currently selected fiscal year (None when creating new)
    if not st.session_state.get("bgi_creating_new") and st.session_state.current_fiscal_year_id is not None:
        existing_grant_info = session.query(GrantInfo).filter_by(
            trustfund_id=effective_trustfund_id,
            fiscal_year_id=st.session_state.current_fiscal_year_id,
            deleted=False
        ).first()
    else:
        existing_grant_info = None

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
                                    (i for i, option in enumerate(data["fiscal_years"]) if option[1] == fiscal_year_id), None),
                                key="bgi_fiscal_year")

    # Update fiscal_year_id
    fiscal_year_id = next((fy[1] for fy in data["fiscal_years"] if fy[0] == fiscal_year), None)

    # P Code Instrument Selection
    p_code_instrument = st.selectbox(
        "Product line/instrument: *",
        ["ASA", "IPF", "PforR", "DPF", "Other"],
        index=["ASA", "IPF", "PforR", "DPF", "Other"].index(p_code_instrument) if p_code_instrument in ["ASA", "IPF", "PforR", "DPF", "Other"] else None,
        key="bgi_p_code_instrument"
    )

    # Handle "Other" selection
    if p_code_instrument == "Other":
        p_code_description = st.text_input("If other, please describe:", value=p_code_description or "", key="bgi_p_code_description")
    else:
        p_code_description = None

    # F4D Association Radio
    f4d_association_value = st.radio(
        "Is the P code only associated with this F4D grant? *",
        ["Yes, this P code is used solely for F4D funded activities",
         "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well."],
        index=None if not f4d_association else ["Yes, this P code is used solely for F4D funded activities",
                                                 "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well."].index(f4d_association),
        key="bgi_f4d_association"
    )

    # Set F4D Association Enum
    if f4d_association_value == "Yes, this P code is used solely for F4D funded activities":
        f4d_association = F4DAssociationEnum.SOLELY_F4D
    elif f4d_association_value == "No, this P code is used for activities supported by other funding sources (e.g., other Trust Funds) as well.":
        f4d_association = F4DAssociationEnum.OTHER_FUNDING
    else:
        f4d_association = None

    # Region Selection.
    # Curate the dropdown: drop the deprecated "Middle East and North Africa"
    # option and give the MENAAP entry a clearer label. Stored value is region_id,
    # so renaming the display text is safe.
    _REGION_DROP = {"middle east and north africa"}
    _REGION_RENAME = {
        "mid east,north africa,afg,pak": "Middle East, North Africa, Afghanistan, & Pakistan",
    }
    region_options = []
    for _name, _rid in data["regions"]:
        _key = (_name or "").strip().lower()
        # Hide the dropped region from new selections, but keep it if it is this
        # record's current region so an existing report isn't silently blanked.
        if _key in _REGION_DROP and _rid != region_id:
            continue
        region_options.append((_REGION_RENAME.get(_key, _name), _rid))

    region = st.selectbox("Region: *",
                            [opt[0] for opt in region_options],
                            index=None if not region_id else next(
                                (i for i, opt in enumerate(region_options) if opt[1] == region_id), None),
                            key="bgi_region")
    # Update region_id
    if region:
        region_id = next((rid for disp, rid in region_options if disp == region), None)

    # Country Selection
    default_countries = country.split(', ') if isinstance(country, str) else country or []
    country = st.multiselect("Country (multiple choice): *", sorted([c[0] for c in data["countries"]]), default=default_countries, key="bgi_country")

    # Pillars Selection
    pillars = st.multiselect("Select the pillar(s) this grant contributes to (multiple choice): *",
                             ["Pillar 1: Strengthening Financial Sector Resiliency",
                              "Pillar 2: Financing the Poor and Vulnerable",
                              "Pillar 3: Financing the Real Economy",
                              "Pillar 4: Developing Financial Markets"],
                             default=pillars,
                             key="bgi_pillars")

    # Explanations
    for pillar in pillars:
        explanation = st.text_area(f"Explain how it contributes to {pillar}", key=pillar, value=pillar_explanations.get(pillar, ""))
        pillar_explanations[pillar] = explanation

    # CCTs Selection
    ccts = st.multiselect("Select the cross-cutting theme(s) this grant contributes to and explain how (multiple choice):",
                          ["Climate change and sustainable finance",
                           "Advancing digitalization",
                           "Financing solutions to close gender gaps"],
                          default=ccts,
                          key="bgi_ccts")

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
                        # grant_info_long.value is TEXT; stringify any remaining
                        # non-string (e.g. region_id int) so Postgres doesn't
                        # infer an integer column type for a mixed batch insert.
                        if value is not None and not isinstance(value, str):
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
                        # grant_info_long.value is TEXT; stringify any remaining
                        # non-string (e.g. region_id int) so Postgres doesn't
                        # infer an integer column type for a mixed batch insert.
                        if value is not None and not isinstance(value, str):
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
                    st.session_state.bgi_creating_new = False
                    st.session_state.bgi_loaded_for_fy = fiscal_year_id
                    st.success("Grant information saved successfully!")
            else:
                st.error(f"Please fill in all mandatory fields: {', '.join(missing_fields)}")

    # Display notification if there are unsaved changes
    if st.session_state.grant_info_unsaved_changes:
        st.warning("⚠️ You have unsaved changes. Don't forget to save your work!")

    session.close()

