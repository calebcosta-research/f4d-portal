# Auto-split from the original monolithic main.py. See git history.
import datetime
import streamlit as st
from model import (
    GrantInfo,
)
from f4d.context import (
    current_team_id,
)


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

