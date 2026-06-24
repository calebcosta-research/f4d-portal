# Auto-split from the original monolithic main.py. See git history.
import ast
import datetime
import streamlit as st
from model import (
    GrantInfo,
)
from f4d.context import (
    current_team_id,
)


def set_blob_entry_archived(session, trustfund_id, fiscal_year_id, field_name,
                            key, archived, create_if_missing=True, reason=None):
    """Toggle the 'archived' flag on one entry inside a serialized dict blob
    (e.g. the 'deliverables' or 'custom_indicators' row) and persist it now.

    Soft-delete: the entry is kept with archived=True rather than removed, so
    it can be restored. Persisting immediately means the archive/restore action
    takes effect on the next rerun without the user clicking the Save button.

    When dropping (archived=True), an optional free-text ``reason`` is stored on
    the entry as 'archive_reason' for the audit trail.

    Returns True if a change was written, False if the key was absent and
    create_if_missing is False (used to discard never-saved draft entries).
    """
    record = (
        session.query(GrantInfo)
        .filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id,
            GrantInfo.field == field_name,
            GrantInfo.deleted == False,
        )
        .first()
    )

    data = {}
    if record and record.value:
        try:
            data = ast.literal_eval(record.value)
        except (ValueError, SyntaxError):
            data = {}
    if not isinstance(data, dict):
        data = {}

    if key not in data and not create_if_missing:
        return False

    entry = data.get(key)
    if not isinstance(entry, dict):
        entry = {}
    entry["archived"] = archived
    if archived and reason:
        entry["archive_reason"] = reason
    data[key] = entry

    now = datetime.datetime.now()
    if record:
        record.value = str(data)
        record.updated_at = now
    else:
        session.add(GrantInfo(
            trustfund_id=trustfund_id, fiscal_year_id=fiscal_year_id,
            field=field_name, value=str(data), team_id=current_team_id(),
            deleted=False, created_at=now, updated_at=now,
        ))
    session.commit()
    return True


def get_long_format_value(session, trustfund_id, fiscal_year_id, field_name, default_value=''):
    """
    Retrieve a specific field value from the long format table
    """
    try:
        result = session.query(GrantInfo).filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id,
            GrantInfo.field == field_name
        ).first()
        
        if result:
            return result.value if result.value is not None else default_value
        else:
            return default_value
    except Exception as e:
        st.error(f"Error retrieving {field_name}: {e}")
        return default_value


def update_long_format_field(session, trustfund_id, fiscal_year_id, field_name, field_value):
    """
    Update or insert a field value in the long format table
    """
    try:
        # Check if the record exists
        existing_record = session.query(GrantInfo).filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id,
            GrantInfo.field == field_name
        ).first()
        
        if existing_record:           
            # Update existing record
            existing_record.value = field_value
            existing_record.updated_at = datetime.datetime.now()
        else:
            # Create new record
            new_record = GrantInfo(
                trustfund_id=trustfund_id,
                fiscal_year_id=fiscal_year_id,
                field=field_name,
                value=field_value,
                team_id=current_team_id(),
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )
            session.add(new_record)
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        st.error(f"Error updating {field_name}: {e}")


def delete_long_format_field(session, trustfund_id, fiscal_year_id):
    try:
        # Assuming your model is named LongFormat and you have a session created
        # Adjust the model name according to your actual database model
        affected_rows = session.query(GrantInfo).filter(
            GrantInfo.trustfund_id == trustfund_id,
            GrantInfo.fiscal_year_id == fiscal_year_id
        ).update({"deleted": True})

        # Commit the changes to the database
        session.commit()
        
    except Exception as e:
        session.rollback()  # Rollback in case of error
        print(f"Error occurred: {e}")


def get_long_format_dict(session, trustfund_id, fiscal_year_id, field_name, default_dict=None):
    """
    Retrieve a dictionary field from long format and safely evaluate it
    """
    if default_dict is None:
        default_dict = {}
    
    try:
        value_str = get_long_format_value(session, trustfund_id, fiscal_year_id, field_name, '{}')
        if value_str and value_str != '{}':
            return eval(value_str)
        else:
            return default_dict
    except Exception as e:
        st.error(f"Error parsing {field_name} dictionary: {e}")
        return default_dict

