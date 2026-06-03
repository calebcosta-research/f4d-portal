# Auto-split from the original monolithic main.py. See git history.
import os
import csv
import ast
import datetime
import streamlit as st
from connection import create_session
from model import (
    F4DAssociationEnum, FiscalYear, GrantInfo, Region, TrustFund,
    Indicator, Country,
)
from f4d.context import (
    current_team_id, current_username,
    current_trustfund_id,
)


def download_grants():
    # Set current_trustfund_id to None when focus lost from New grant reporting page
    st.session_state.current_trustfund_id = None
    st.session_state.current_fiscal_year_id = None
    
    session = create_session()
    team_id=current_team_id()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if st.button("Export Indicators", type="primary"):
        export_grants_indicator(
            session, f"Indicator_{timestamp}.csv", team_id=team_id, trustfund_id=current_trustfund_id())

    if st.button("Export Outputs/deliverables", type="primary"):
        export_grants_deliverable(
            session, f"Deliverable_{timestamp}.csv", team_id=team_id, trustfund_id=current_trustfund_id())


def read_data():
    # Function to fetch trustfunds from the database
    def fetch_trustfunds():
        session = create_session()
        try:
            # Query to select trustfunds
            trustfunds = session.query(TrustFund.id, TrustFund.name, TrustFund.grant).filter(
                TrustFund.project_type == 'Trust Fund', TrustFund.deleted == False, TrustFund.team_id == current_team_id(), TrustFund.name == current_username()).all()
            # Extract trustfunds from tuples
            return [(f"{trustfund[1]} - {trustfund[2]}", trustfund[0]) for trustfund in trustfunds]
        except Exception as e:
            print(f"Error fetching trustfunds: {e}")
            return []
        finally:
            session.close()

    # Fetch the trustfunds
    trustfunds = fetch_trustfunds()

    # Function to fetch countries from the database

    def fetch_countries():
        session = create_session()
        try:
            # Query to select countries
            countries = session.query(Country.id, Country.country).all()
            # Extract coutry from tuples
            return [(country[1], country[0]) for country in countries]
        except Exception as e:
            print(f"Error fetching pcodes: {e}")
            return []
        finally:
            session.close()  # Ensure the session is closed

    # Fetch the countries
    countries = fetch_countries()

    # Function to fetch regions from the database

    def fetch_regions():
        session = create_session()
        try:
            # Query to select regions
            regions = session.query(Region.id, Region.region).all()
            # Extract region from tuples
            return [(region[1], region[0]) for region in regions]
        except Exception as e:
            print(f"Error fetching regions: {e}")
            return []
        finally:
            session.close()

    # Fetch the regions
    regions = fetch_regions()

    # Function to fetch fiscalyears from the database

    def fetch_fiscalyears():
        session = create_session()
        try:
            # Query to select fiscalyears
            fys = session.query(FiscalYear.id, FiscalYear.fy).filter(
                FiscalYear.deleted == False).all()
            # Extract region from tuples
            return [(fy[1], fy[0]) for fy in fys]
        except Exception as e:
            print(f"Error fetching fiscal years: {e}")
            return []
        finally:
            session.close()

    # Fetch the fiscalyears
    fys = fetch_fiscalyears()

    # Return the fetched data as a dictionary (or tuple)
    return {
        "trustfunds": trustfunds,
        "countries": countries,
        "regions": regions,
        "fiscal_years": fys
    }


def export_grants_deliverable(session, filename, team_id, trustfund_id=None):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "deliverable_name", "deliverable_input_value", "deliverable_progress", "deliverable_quantity", "deliverable_description", "deliverable_data_source", "deliverable_next_steps", "deliverable_supporting_materials_url"
    ]

    # Fetch all records from the GrantInfo table in long format
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, 
        GrantInfo.deleted == False, 
        GrantInfo.trustfund_id==trustfund_id).all()

    # Group records by trustfund_id and fiscal_year_id to reconstruct wide format
    grouped_grants = {}
    for grant_info in grant_infos:
        key = (grant_info.trustfund_id, grant_info.fiscal_year_id)
        if key not in grouped_grants:
            grouped_grants[key] = {}
        grouped_grants[key][grant_info.field] = grant_info


    # Prepare data for CSV
    csv_data = []
    
    for (trustfund_id, fiscal_year_id), grant_fields in grouped_grants.items():
        try:
            # Reconstruct the grant info from long format fields
            reconstructed_grant = type('GrantInfo', (), {
                'trustfund_id': trustfund_id,
                'fiscal_year_id': fiscal_year_id
            })()

            # Extract field values from long format
            country = grant_fields.get('country').value if 'country' in grant_fields else ''
            region_id = grant_fields.get('region_id').value if 'region_id' in grant_fields else None
            p_code_instrument = grant_fields.get('p_code_instrument').value if 'p_code_instrument' in grant_fields else ''
            p_code_description = grant_fields.get('p_code_description').value if 'p_code_description' in grant_fields else ''
            f4d_association = grant_fields.get('f4d_association').value if 'f4d_association' in grant_fields else None
            pillars = grant_fields.get('pillars').value if 'pillars' in grant_fields else ''
            ccts = grant_fields.get('ccts').value if 'ccts' in grant_fields else ''
            
            # Parse JSON fields
            pillar_explanations_str = grant_fields.get('pillar_explanations').value if 'pillar_explanations' in grant_fields else '{}'
            cct_explanations_str = grant_fields.get('cct_explanations').value if 'cct_explanations' in grant_fields else '{}'
            operations_str = grant_fields.get('operations').value if 'operations' in grant_fields else '{}'
            cpfs_str = grant_fields.get('cpfs').value if 'cpfs' in grant_fields else '{}'
            deliverables_str = grant_fields.get('deliverables').value if 'deliverables' in grant_fields else '{}'
            
            # Parse other fields
            challenges = grant_fields.get('challenges').value if 'challenges' in grant_fields else ''
            strategic_objective = grant_fields.get('strategic_objective').value if 'strategic_objective' in grant_fields else ''
            overall_progress = grant_fields.get('overall_progress').value if 'overall_progress' in grant_fields else ''
            implementation_challenges = grant_fields.get('implementation_challenges').value if 'implementation_challenges' in grant_fields else ''
            public_communication_external = grant_fields.get('public_communication_external').value if 'public_communication_external' in grant_fields else ''
            public_communication_internal = grant_fields.get('public_communication_internal').value if 'public_communication_internal' in grant_fields else ''
            collaborations = grant_fields.get('collaborations').value if 'collaborations' in grant_fields else ''
            other_teams = grant_fields.get('other_teams').value if 'other_teams' in grant_fields else ''
            other_ifis = grant_fields.get('other_ifis').value if 'other_ifis' in grant_fields else ''
            other_orgs = grant_fields.get('other_orgs').value if 'other_orgs' in grant_fields else ''
            describe_collaboration = grant_fields.get('describe_collaboration').value if 'describe_collaboration' in grant_fields else ''
            lessons_learned = grant_fields.get('lessons_learned').value if 'lessons_learned' in grant_fields else ''
            
            # Check each field for None before evaluating
            pillar_explanations_dict = ast.literal_eval(pillar_explanations_str) if pillar_explanations_str and pillar_explanations_str != '{}' else {}
            cct_explanations_dict = ast.literal_eval(cct_explanations_str) if cct_explanations_str and cct_explanations_str != '{}' else {}
            operations_dict = ast.literal_eval(operations_str) if operations_str and operations_str != '{}' else {}
            cpfs_dict = ast.literal_eval(cpfs_str) if cpfs_str and cpfs_str != '{}' else {}
            deliverables_dict = ast.literal_eval(deliverables_str) if deliverables_str and deliverables_str != '{}' else {}

            region_name = ''
            if region_id:
                region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                if region:
                    region_name = region.region

            trustfund_name = ''
            if reconstructed_grant.trustfund_id:
                tf = session.query(TrustFund).filter_by(id=reconstructed_grant.trustfund_id, deleted=False).first()
                if tf:
                    trustfund_name = tf.name

            fiscal_year = ''
            if reconstructed_grant.fiscal_year_id:
                fy = session.query(FiscalYear).filter_by(id=reconstructed_grant.fiscal_year_id, deleted=False).first()
                if fy:
                    fiscal_year = fy.fy

            # Create a base row without deliverables
            base_row = {
                "trustfund": trustfund_name,
                "fiscal_year": fiscal_year,
                "country": country,
                "p_code_instrument": p_code_instrument,
                "p_code_description": p_code_description,
                "f4d_association": (
                    F4DAssociationEnum(f4d_association).value
                    if f4d_association is not None else None
                ),
                "region": region_name,
                "pillars": pillars,
                "ccts": ccts,
                "pillar_1_explanation": pillar_explanations_dict.get("Pillar 1: Strengthening Financial Sector Resiliency", ""),
                "pillar_2_explanation": pillar_explanations_dict.get("Pillar 2: Financing the Poor and Vulnerable", ""),
                "pillar_3_explanation": pillar_explanations_dict.get("Pillar 3: Financing the Real Economy", ""),
                "pillar_4_explanation": pillar_explanations_dict.get("Pillar 4: Developing Financial Markets", ""),
                "cct_explanation_1": cct_explanations_dict.get("Climate change and sustainable finance", ""),
                "cct_explanation_2": cct_explanations_dict.get("Advancing digitalization", ""),
                "cct_explanation_3": cct_explanations_dict.get("Financing solutions to close gender gaps", ""),
                "challenges": challenges,
                "strategic_objective": strategic_objective,
                "overall_progress": overall_progress,
                "implementation_challenges": implementation_challenges,
                "public_communication_external": public_communication_external,
                "public_communication_internal": public_communication_internal,
                "collaborations": collaborations,
                "other_teams": other_teams,
                "other_ifis": other_ifis,
                "other_orgs": other_orgs,
                "describe_collaboration": describe_collaboration,
                "lessons_learned": lessons_learned
            }
            
            # Handle operations dynamically
            if operations_dict:
                for key, value in operations_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            base_row[f"operation_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"operation_{nested_key}_{key}" not in headers:
                                headers.append(f"operation_{nested_key}_{key}")

            # Handle CPFS dynamically
            if cpfs_dict:
                for key, value in cpfs_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            base_row[f"cpf_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"cpf_{nested_key}_{key}" not in headers:
                                headers.append(f"cpf_{nested_key}_{key}")

            indicators = session.query(Indicator).filter(
                Indicator.team_id == team_id, Indicator.deleted == False).all()

            indicator_name_map = {
                indicator.id: {
                    "custom_name": indicator.indicator_name,
                } for indicator in indicators
            }

            # Handle deliverables dynamically
            if deliverables_dict:
                for key, value in deliverables_dict.items():
                    if key and isinstance(value, dict):
                        # Get standard and custom names from the mapping
                        indicator_info = indicator_name_map.get(
                            int(key), {"custom_name": ""})

                        deliverable_name = indicator_info["custom_name"]

                        # Access the nested value directly from `value`
                        deliverable_info = value

                        # Ensure deliverable_info is a dictionary
                        if isinstance(deliverable_info, dict):
                            # Create a new row for each deliverable
                            deliverable_row = base_row.copy()  # Copy the base row
                            deliverable_row["deliverable_name"] = deliverable_name
                            deliverable_row["deliverable_input_value"] = deliverable_info.get(
                                "input_value", "")
                            deliverable_row["deliverable_progress"] = deliverable_info.get(
                                "progress", "")
                            deliverable_row["deliverable_quantity"] = deliverable_info.get(
                                "deliverable_quantity", "")
                            deliverable_row["deliverable_description"] = deliverable_info.get(
                                "description", "")
                            deliverable_row["deliverable_data_source"] = deliverable_info.get(
                                "data_source", "")
                            deliverable_row["deliverable_next_steps"] = deliverable_info.get(
                                "next_steps", "")
                            deliverable_row["deliverable_supporting_materials_url"] = deliverable_info.get(
                                "supporting_materials_url", "")

                            # Append the deliverable row to csv_data
                            csv_data.append(deliverable_row)
            else:
                # If no deliverables, add the base row
                csv_data.append(base_row)

        except Exception as e:
            print(f"Error processing grant info for trustfund_id {trustfund_id}, fiscal_year_id {fiscal_year_id}: {e}")


    # Write data to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for data in csv_data:
            writer.writerow(data)
        st.success("Data have been exported!")

    # Read the CSV file to provide for download
    with open(filename, "rb") as f:
        csv_file = f.read()

    # Use st.download_button to allow file download
    st.download_button(
        label="Download CSV",
        data=csv_file,
        file_name=filename,
        mime='text/csv'
    )

    # Delete the file after download
    os.remove(filename)


def export_grants_indicator(session, filename, team_id, trustfund_id=None):
    # Specify the column headers for the CSV
    headers = [
        "trustfund", "fiscal_year", "country",
        "p_code_instrument", "p_code_description", "f4d_association",
        "region", "pillars", "ccts", "pillar_1_explanation", "pillar_2_explanation",
        "pillar_3_explanation", "pillar_4_explanation",
        "cct_explanation_1", "cct_explanation_2", "cct_explanation_3",
        "challenges", "strategic_objective", "overall_progress", "implementation_challenges",
        "public_communication_external", "public_communication_internal",
        "collaborations", "other_teams", "other_ifis", "other_orgs", "describe_collaboration", "lessons_learned",
        "indicator_name", "indicator_input_value", "indicator_baseline_value", "indicator_year_baseline", "indicator_progress", "indicator_target_value", "indicator_year_target", "indicator_data_collection", "indicator_level_of_result"
    ]

    # Fetch all records from the GrantInfo table in long format
    grant_infos = session.query(GrantInfo).filter(
        GrantInfo.team_id == team_id, GrantInfo.deleted == False, GrantInfo.trustfund_id==trustfund_id).all()

    # Group records by trustfund_id and fiscal_year_id to reconstruct wide format
    grouped_grants = {}
    for grant_info in grant_infos:
        key = (grant_info.trustfund_id, grant_info.fiscal_year_id)
        if key not in grouped_grants:
            grouped_grants[key] = {}
        grouped_grants[key][grant_info.field] = grant_info

    # Prepare data for CSV
    csv_data = []

    for (trustfund_id, fiscal_year_id), grant_fields in grouped_grants.items():

        try:
            # Reconstruct the grant info from long format fields
            reconstructed_grant = type('GrantInfo', (), {
                'trustfund_id': trustfund_id,
                'fiscal_year_id': fiscal_year_id
            })()

            # Extract field values from long format
            country = grant_fields.get('country').value if 'country' in grant_fields else ''
            region_id = grant_fields.get('region_id').value if 'region_id' in grant_fields else None
            p_code_instrument = grant_fields.get('p_code_instrument').value if 'p_code_instrument' in grant_fields else ''
            p_code_description = grant_fields.get('p_code_description').value if 'p_code_description' in grant_fields else ''
            f4d_association = grant_fields.get('f4d_association').value if 'f4d_association' in grant_fields else None
            pillars = grant_fields.get('pillars').value if 'pillars' in grant_fields else ''
            ccts = grant_fields.get('ccts').value if 'ccts' in grant_fields else ''
            
            # Parse JSON fields
            pillar_explanations_str = grant_fields.get('pillar_explanations').value if 'pillar_explanations' in grant_fields else '{}'
            cct_explanations_str = grant_fields.get('cct_explanations').value if 'cct_explanations' in grant_fields else '{}'
            operations_str = grant_fields.get('operations').value if 'operations' in grant_fields else '{}'
            cpfs_str = grant_fields.get('cpfs').value if 'cpfs' in grant_fields else '{}'
            custom_indicators_str = grant_fields.get('custom_indicators').value if 'custom_indicators' in grant_fields else '{}'
            
            # Parse other fields
            challenges = grant_fields.get('challenges').value if 'challenges' in grant_fields else ''
            strategic_objective = grant_fields.get('strategic_objective').value if 'strategic_objective' in grant_fields else ''
            overall_progress = grant_fields.get('overall_progress').value if 'overall_progress' in grant_fields else ''
            implementation_challenges = grant_fields.get('implementation_challenges').value if 'implementation_challenges' in grant_fields else ''
            public_communication_external = grant_fields.get('public_communication_external').value if 'public_communication_external' in grant_fields else ''
            public_communication_internal = grant_fields.get('public_communication_internal').value if 'public_communication_internal' in grant_fields else ''
            collaborations = grant_fields.get('collaborations').value if 'collaborations' in grant_fields else ''
            other_teams = grant_fields.get('other_teams').value if 'other_teams' in grant_fields else ''
            other_ifis = grant_fields.get('other_ifis').value if 'other_ifis' in grant_fields else ''
            other_orgs = grant_fields.get('other_orgs').value if 'other_orgs' in grant_fields else ''
            describe_collaboration = grant_fields.get('describe_collaboration').value if 'describe_collaboration' in grant_fields else ''
            lessons_learned = grant_fields.get('lessons_learned').value if 'lessons_learned' in grant_fields else ''

            # Check each field for None before evaluating
            pillar_explanations_dict = ast.literal_eval(pillar_explanations_str) if pillar_explanations_str and pillar_explanations_str != '{}' else {}
            cct_explanations_dict = ast.literal_eval(cct_explanations_str) if cct_explanations_str and cct_explanations_str != '{}' else {}
            operations_dict = ast.literal_eval(operations_str) if operations_str and operations_str != '{}' else {}
            cpfs_dict = ast.literal_eval(cpfs_str) if cpfs_str and cpfs_str != '{}' else {}
            custom_indicators_dict = ast.literal_eval(custom_indicators_str) if custom_indicators_str and custom_indicators_str != '{}' else {}

            region_name = ''
            if region_id:
                region = session.query(Region).filter_by(id=region_id, deleted=False).first()
                if region:
                    region_name = region.region

            trustfund_name = ''
            if reconstructed_grant.trustfund_id:
                tf = session.query(TrustFund).filter_by(id=reconstructed_grant.trustfund_id, deleted=False).first()
                if tf:
                    trustfund_name = tf.name

            fiscal_year = ''
            if reconstructed_grant.fiscal_year_id:
                fy = session.query(FiscalYear).filter_by(id=reconstructed_grant.fiscal_year_id, deleted=False).first()
                if fy:
                    fiscal_year = fy.fy

            # Create base row
            row = {
                "trustfund": trustfund_name,
                "fiscal_year": fiscal_year,
                "country": country,
                "region": region_name,
                "p_code_instrument": p_code_instrument,
                "p_code_description": p_code_description,
                "f4d_association": (
                    F4DAssociationEnum(f4d_association).value
                    if f4d_association is not None else None
                ),

                "pillars": pillars,
                "ccts": ccts,
                "pillar_1_explanation": pillar_explanations_dict.get("Pillar 1: Strengthening Financial Sector Resiliency", ""),
                "pillar_2_explanation": pillar_explanations_dict.get("Pillar 2: Financing the Poor and Vulnerable", ""),
                "pillar_3_explanation": pillar_explanations_dict.get("Pillar 3: Financing the Real Economy", ""),
                "pillar_4_explanation": pillar_explanations_dict.get("Pillar 4: Developing Financial Markets", ""),
                "cct_explanation_1": cct_explanations_dict.get("Climate change and sustainable finance", ""),
                "cct_explanation_2": cct_explanations_dict.get("Advancing digitalization", ""),
                "cct_explanation_3": cct_explanations_dict.get("Financing solutions to close gender gaps", ""),
                "challenges": challenges,
                "strategic_objective": strategic_objective,
                "overall_progress": overall_progress,
                "implementation_challenges": implementation_challenges,
                "public_communication_external": public_communication_external,
                "public_communication_internal": public_communication_internal,
                "collaborations": collaborations,
                "other_teams": other_teams,
                "other_ifis": other_ifis,
                "other_orgs": other_orgs,
                "describe_collaboration": describe_collaboration,
                "lessons_learned": lessons_learned
            }

            # Handle operations dynamically
            if operations_dict:
                for key, value in operations_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            row[f"operation_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"operation_{nested_key}_{key}" not in headers:
                                headers.append(f"operation_{nested_key}_{key}")

            # Handle CPFS dynamically
            if cpfs_dict:
                for key, value in cpfs_dict.items():
                    if key and isinstance(value, dict):
                        for nested_key in value:
                            row[f"cpf_{nested_key}_{key}"] = value[nested_key] if value[nested_key] is not None else ""
                            if f"cpf_{nested_key}_{key}" not in headers:
                                headers.append(f"cpf_{nested_key}_{key}")

            indicators = session.query(Indicator).filter(
                Indicator.team_id == team_id, Indicator.deleted == False).all()

            indicator_name_map = {
                indicator.id: {
                    "custom_name": indicator.indicator_name
                } for indicator in indicators
            }

            # Handle indicators dynamically
            if custom_indicators_dict:
                for key, value in custom_indicators_dict.items():
                    if key and isinstance(value, dict):
                        # Get standard and custom names from the mapping
                        indicator_info = indicator_name_map.get(
                            int(key), {"custom_name": ""})
                        custom_indicator_name = indicator_info["custom_name"]


                        # Access the nested value directly from `value`
                        indicator_info = value
                        # Ensure indicator_info is a dictionary
                        if isinstance(indicator_info, dict):
                            # Create a new row for each indicator
                            indicator_row = row.copy()  # Copy the base row
                            indicator_row["indicator_name"] = custom_indicator_name
                            indicator_row["indicator_input_value"] = indicator_info.get(
                                "input_value", "")
                            indicator_row["indicator_baseline_value"] = indicator_info.get(
                                "baseline_value", "")
                            indicator_row["indicator_year_baseline"] = indicator_info.get(
                                "year_baseline", "")
                            indicator_row["indicator_progress"] = indicator_info.get(
                                "progress", "")
                            indicator_row["indicator_target_value"] = indicator_info.get(
                                "target_value", "")
                            indicator_row["indicator_year_target"] = indicator_info.get(
                                "year_target", "")
                            indicator_row["indicator_data_collection"] = indicator_info.get(
                                "data_collection", "")
                            indicator_row["indicator_level_of_result"] = indicator_info.get(
                                "level_of_result", "")

                            # Append the indicator row to csv_data
                            csv_data.append(indicator_row)
            else:
                # If no indicators, add the base row
                csv_data.append(row)

        except Exception as e:
            print(f"Error processing grant info for trustfund_id {trustfund_id}, fiscal_year_id {fiscal_year_id}: {e}")


    # Write data to CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for data in csv_data:
            writer.writerow(data)
        st.success("Data have been exported!")

    # Read the CSV file to provide for download
    with open(filename, "rb") as f:
        csv_file = f.read()

    # Use st.download_button to allow file download
    st.download_button(
        label="Download CSV",
        data=csv_file,
        file_name=filename,
        mime='text/csv'
    )

    # Delete the file after download
    os.remove(filename)

