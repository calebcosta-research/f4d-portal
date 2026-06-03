# Auto-split from the original monolithic main.py. See git history.
import streamlit as st
from f4d.context import (
    current_username, current_grantname,
)


def home():
    st.session_state.current_trustfund_id = None
    st.session_state.current_fiscal_year_id = None
    st.success("# F4D Results Reporting")
    st.write(
        """
This form aims to gather information on F4D financed activities for the F4D Annual Report. It will be used to record progress of the F4D umbrella, which is a mandatory donor reporting requirement. Note that the information in this form may be made public, hence please indicate clearly in case anything reported here should be treated confidentially. \n
TTLs of F4D grants are requested to review the pre-filled sections and to insert requested information. For any questions reach out to: F4DUmbrella@worldbank.org \n

""")
    
    st.write("""
             <h2>Instructions for Using the F4D Results Reporting</h2>
<h5>Pages and Sections</h5>
The application is organized into multiple pages, one of them containing specific sections (subpages) to help you manage grant information effectively.
             <p></p>

<u>Home:</u> Overview and instruction.<br/>
<u>Report new results:</u> Where you can enter and manage grant details.<br/>
<i>Basic Grant Information:</i> Enter basic details about the grant.<br/>
<i>Strategic Objective & Progress:</i> Define the strategic objectives and progress of the grant.<br/>
<i>Lending Operations:</i> Manage lending operations related to the grant.<br/>
<i>Collaboration/Partnership:</i> Manage collaboration and partnership details.<br/>
<i>Outputs/deliverables:</i> Enter and manage outputs and deliverables.<br/>
<i>Results Indicators:</i> Define and manage results indicators for the grant.<br/>
<u>Download results:</u> Download grant data in CSV formats.<br/>

             
<h5>Important Notes</h5>
Single Record Saving: You can only save one record for each combination of Grant ID and fiscal year. Ensure that the details are correct before saving.<br/>
Data Protection: Make sure to save your results frequently to avoid losing any data. Click the “Save” button regularly.<br/>

<p></p>             
<h5>Session Management</h5>
Navigating Between Sections: You can navigate between sections without losing your data. Your session will remain active, and all entered data will be retained.<br/>
Navigating Between Pages: Be cautious when switching between different pages, as this will reset your session and you may lose any unsaved data.<br/>

<p></p>               
<h5>User Association</h5>
Each Grant ID is associated with a single user. This ensures that data entry remains organized and unique to each user.<br/>

<p></p>
<h5>Troubleshooting</h5>
If you encounter any bugs or errors while using the application, please contact fkurbonov1@worldbank.org for assistance.<br/>
<p></p>
             """, unsafe_allow_html=True)

    # Display the current user's username
    st.write(f"**Current User:** {current_username()}")
    
    # Display the current grant name
    st.write(f"**Current Grant Name:** {current_grantname()}")

