# Azure provisioning request — F4D Results Reporting portal

**To:** [Azure platform / cloud team]
**From:** [your name]
**Subject:** Provision App Service + PostgreSQL for the F4D Results Reporting portal (dev)

My account (roles: *WBG-appservices-developer-role*, *DocumentDB Account Contributor*,
*Storage Blob Data Contributor*, *Reader*) can deploy into App Services but cannot
**create** App Services or databases. Could you provision the following in the **`dev`**
resource group and grant me deploy + configuration rights on them?

### 1. App Service (to run the app)
- **App Service Plan:** Linux, **B1 Basic** (or higher), region [our standard region]
- **Web App:** Linux, **Python 3.11**, name e.g. `f4d-portal`
- **WebSockets:** **On** (the app — Streamlit — needs them)
- **Access I need:** ability to deploy code (ZIP/Git) and edit Application Settings + the Startup Command

### 2. Database (to store the data)
- **Azure Database for PostgreSQL — flexible server**
- **Tier:** Burstable **B1ms** (1 vCore, 2 GiB), 32 GiB storage, HA off
- **PostgreSQL version:** 16
- **Auth:** PostgreSQL authentication — admin login + password (please share securely, or set it and grant me access)
- **Networking:** Public access, with **"Allow public access from any Azure service within Azure"** enabled (so the App Service can connect), plus a firewall rule for my client IP so I can load the initial data

### Notes
- Data is internal M&E reporting, **non-classified**, a few MB in size.
- If a flexible server isn't possible, an Azure SQL Database also works (the app supports both) — but PostgreSQL flexible server is the simplest.
- Once provisioned, I'll handle deployment and configuration myself.

Thanks!
