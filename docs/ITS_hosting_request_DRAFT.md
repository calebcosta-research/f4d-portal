# DRAFT — Email/ticket to WB ITS: hosting & data classification for the F4D Results Reporting portal

> Fill the **[bracketed]** placeholders before sending. Pick the email OR the ticket-bullets version.

---

## Version A — Email

**To:** [ITS focal point / your unit's ITS business partner]
**Cc:** [your manager / program lead]
**Subject:** Hosting & data-classification guidance for a new internal M&E reporting app (Python/Streamlit)

Hi [Name],

My team has built an internal web application — the **F4D Results Reporting portal** — that lets World Bank Task Teams submit and review M&E results and deliverable updates. We're now ready to move it from local development toward a properly hosted, compliant deployment, and I'd like your guidance before we go further.

**About the app**
- **Stack:** Python (Streamlit front end), SQLAlchemy ORM, designed for **SQL Server / Azure SQL** as the backing database. Currently runs locally against SQLite for development only.
- **Users:** World Bank staff (Task Team Leads and program admins). Access should be limited to authenticated WB staff — not public.
- **Data:** M&E results — grant/trust-fund metadata, narrative progress, indicators, and deliverables. We are **still confirming the data classification** (see question 1) and want to host it to the correct standard from day one.

**What I need from you**
1. **Classification:** Based on the data described above, what classification should this fall under (Official Use Only vs. Confidential)? If you need a field list to decide, I can provide one.
2. **Approved hosting pattern:** For data at that classification, what's the approved way to host a Python web app in our environment — Azure App Service / Container Apps in the WB tenant, an internal VM, or another standard? It should be reachable by WB staff but not exposed publicly.
3. **Database:** Can we get a managed **Azure SQL** instance provisioned (encryption at rest enabled), and who would own backups and patching?
4. **Authentication:** Is **Entra ID (Azure AD) SSO** the required/expected sign-in method? If so, who sets up the application registration? (We'd prefer SSO over the app managing its own passwords.)
5. **Process & timeline:** What's the onboarding / security-assessment process before go-live, and roughly how long does it take, so I can plan our rollout?

Happy to walk through the app on a quick call. Thanks very much for the help.

Best,
[Your name]
[Team / unit]

---

## Version B — Service-desk ticket (bullet form)

- **Request:** Hosting + data-classification guidance for an internal M&E web app, before production deployment.
- **App:** "F4D Results Reporting portal." Python/Streamlit + SQLAlchemy; targets SQL Server / Azure SQL. Currently local/SQLite dev only.
- **Users:** Authenticated WB staff (TTLs + admins). Not public.
- **Data:** M&E results — grant/trust-fund metadata, narrative progress, indicators, deliverables. Classification not yet confirmed.
- **Need:**
  1. Confirm data classification (Official Use Only vs. Confidential).
  2. Approved hosting pattern for that classification (App Service / Container Apps / internal VM), WB-network-only.
  3. Managed Azure SQL instance (TDE on); owner for backups/patching.
  4. Confirm Entra ID SSO as auth method + who creates the app registration.
  5. App onboarding / security-assessment process and expected timeline to go-live.

---

### Notes for you (not part of the email)
- If classification comes back **Official Use Only** rather than Confidential, hosting options widen — but Entra ID SSO + WB-network-only is still the sensible default, and we should still fix the two security issues before go-live regardless.
- Before any WB security assessment, the app needs: **password hashing or SSO** (currently plaintext), and **`eval()` removed** (currently executes stored DB values). These will be flagged in any review.
