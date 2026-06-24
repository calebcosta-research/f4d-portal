"""Seed the Haiti example grant (TF0B9226) from the F4D master dataset.

Content transcribed from F4D_rd_master.xlsx (sheets 'Deliverables' + 'Results',
Trust Fund Number TF0B9226), reported "as of June 30, 2025" -> seeded as the
FY25 report. Grant metadata (Pcode P179567, LAC region, TTLs, objective) also
from that file.

Clean rebuild: this script WIPES the Haiti grant's indicators, mappings, and
saved report rows, then recreates them, so re-running always reproduces exactly
the master's content (no stale rows from earlier hand-built versions).

Fiscal years seeded: FY24, FY25, FY26 (FY26 added for upcoming reporting).

Demo login:  username = haiti_demo   password = demo123

    ./venv/Scripts/python.exe seed_haiti_example.py
"""
import datetime

from connection import create_session
from model import (
    Team, User, FiscalYear, TrustFund, Indicator, TrustFundIndicatorMapping,
    Region, Country, GrantInfo,
)

NOW = datetime.datetime.now()
TTL_USERNAME = "haiti_demo"          # MUST equal the trust fund name (context binding)
TTL_PASSWORD = "demo123"
GRANT_NUMBER = "TF0B9226"
PCODE = "P179567"
GRANT_DISPLAY = "Digital Financial Services and Remittances in Haiti"
TTL_NAMES = "Helen Luskin Gradstein; Olivia-Kelly Lonkeu; Ailo Klara Manigat"
OBJECTIVE = ("Strengthen the capacity of the Government of Haiti to expand "
             "access to digital payments and remittances for households.")
TARGET_FY = "FY25"
FISCAL_YEARS = ("FY24", "FY25", "FY26")
CATEGORIES = "Completed, In Progress, Not Started"
DELIVERABLE_CATEGORIES = ("Completed", "In Progress", "Not Started")


def progress_category(progress_clean):
    """Map the master's Progress_clean column onto the deliverable's three
    categories. Only values that fit prepopulate the dropdown; anything else
    (Planned, On Hold, Canceled, Unknown, blank, ...) returns "" so the field
    is left unselected. "Complete" is treated as "Completed".
    """
    if not progress_clean:
        return ""
    value = progress_clean.strip()
    if value.lower() in ("complete", "completed"):
        return "Completed"
    if value in DELIVERABLE_CATEGORIES:
        return value
    return ""


# (indicator_id, name, Progress_clean raw value, description, data source, has media?, standard indicator)
DELIVERABLES = [
    ("TF0B9226 - D1", "Financial Literacy Modules for Remittances", "Complete",
     "The financial literacy modules include content to promote remittances, "
     "including their digital termination.",
     "World Bank SharePoint (project P179567)", "Yes",
     "Number of beneficiary countries supported with financial education initiatives"),
    ("TF0B9226 - D2",
     "Drafting inputs to DFS and remittances legal and regulatory framework", "In Progress",
     "Drafting inputs to DFS and remittances legal and regulatory framework; "
     "likely various legal instruments.",
     "Presentation to new staff in January 2025 for follow-on work", "Yes", None),
    ("TF0B9226 - D3",
     "Assessment of DFS Core and Ancillary Infrastructure and Legal Framework, "
     "and Remittances Assessment", "Complete",
     "The assessment with a roadmap analyzes the core and ancillary DFS "
     "infrastructure and legal framework, along with the remittances context, "
     "to assess how to promote digital payments and remittances in Haiti.",
     "Presentation to new staff in January 2025", "Yes",
     "Number of beneficiary countries supported to improve financial "
     "infrastructures for payments and digital financial services"),
    ("TF0B9226 - D4", "Remittances Assessment", "Complete",
     "Assessment report on the basis of the CPMI - World Bank General "
     "Principles for International Remittance Services.",
     "Included in the overall DFS assessment presented in January 2025", "Yes",
     "Number of beneficiary countries supported to improve financial "
     "infrastructures for payments and digital financial services"),
]

# (indicator_id, name, unit, input value, baseline, target, data collection, standard indicator, level)
RESULTS_INDICATORS = [
    ("TF0B9226 - RI1", "Cost of sending remittances to Haiti", "Number",
     6.3, "7.6", "7.2", "ICT / Remittance Prices Worldwide",
     "Cost of sending $200 in remittances", "Outcome"),
    ("TF0B9226 - RI2", "Drafting Inputs to DFS and remittances legal framework", "Number",
     3, "0", "3", "Project records", None, "Output"),
]


def get_or_create(session, model, defaults=None, **filters):
    instance = session.query(model).filter_by(**filters).first()
    if instance:
        return instance, False
    instance = model(**{**filters, **(defaults or {})})
    session.add(instance)
    session.flush()
    return instance, True


def main():
    session = create_session()
    try:
        team, _ = get_or_create(session, Team, team="Haiti DFS Team",
                                defaults={"created_at": NOW, "updated_at": NOW})
        get_or_create(session, User, username=TTL_USERNAME,
                      defaults={"password": TTL_PASSWORD, "team_id": team.id,
                                "created_at": NOW, "updated_at": NOW})

        fys = {}
        for label in FISCAL_YEARS:
            fy, _ = get_or_create(session, FiscalYear, fy=label,
                                  defaults={"created_at": NOW, "updated_at": NOW})
            fys[label] = fy

        # Trust fund name MUST equal the username (context resolution); refresh metadata.
        trustfund, _ = get_or_create(
            session, TrustFund, name=TTL_USERNAME, team_id=team.id,
            defaults={"project_type": "Trust Fund", "created_at": NOW, "updated_at": NOW})
        trustfund.grant = GRANT_NUMBER
        trustfund.pcode = PCODE
        trustfund.description = GRANT_DISPLAY
        trustfund.ttl = TTL_NAMES
        trustfund.project_type = "Trust Fund"
        trustfund.updated_at = NOW

        region, _ = get_or_create(session, Region, region="Latin America and Caribbean",
                                  defaults={"created_at": NOW, "updated_at": NOW})
        get_or_create(session, Country, country="Haiti",
                      defaults={"created_at": NOW, "updated_at": NOW})

        # --- Clean rebuild: wipe this grant's content so re-runs are deterministic ---
        session.flush()
        session.query(GrantInfo).filter_by(trustfund_id=trustfund.id).delete(synchronize_session=False)
        session.query(TrustFundIndicatorMapping).filter_by(trustfund_id=trustfund.id).delete(synchronize_session=False)
        session.query(Indicator).filter_by(team_id=team.id).delete(synchronize_session=False)
        session.flush()

        def add_indicator(ind_id, name, prompt, unit, std, custom, categorical=None):
            ind = Indicator(
                indicator_id=ind_id, indicator_name=name, indicator_prompt=prompt,
                unit_of_measurement=unit, categorical_unit=categorical,
                standard_indicator_name=std, custom_indicator=custom,
                team_id=team.id, created_at=NOW, updated_at=NOW)
            session.add(ind)
            session.flush()
            session.add(TrustFundIndicatorMapping(
                trustfund_id=trustfund.id, indicator_id=ind.id, relation_ship="Mandatory",
                team_id=team.id, created_at=NOW, updated_at=NOW))
            return ind

        results = {r[0]: add_indicator(r[0], r[1], r[1], r[2], r[7], True)
                   for r in RESULTS_INDICATORS}
        deliverables = {d[0]: add_indicator(d[0], d[1], "Progress Update", "Categorical",
                                            d[6], False, categorical=CATEGORIES)
                        for d in DELIVERABLES}
        session.flush()

        fy25 = fys[TARGET_FY]

        def add_field(field, value):
            session.add(GrantInfo(
                trustfund_id=trustfund.id, fiscal_year_id=fy25.id, field=field, value=value,
                team_id=team.id, deleted=False, created_at=NOW, updated_at=NOW))

        # --- Basic grant information ---
        add_field("p_code_instrument", "ASA")
        add_field("country", "Haiti")
        add_field("f4d_association",
                  "Yes, this P code is used solely for F4D funded activities")
        add_field("region_id", str(region.id))
        add_field("pillars", "Pillar 2: Financing the Poor and Vulnerable")
        add_field("ccts", "Advancing digitalization, Financing solutions to close gender gaps")

        # --- Strategic objective (from the grant's Objective) ---
        add_field("strategic_objective", OBJECTIVE)

        # --- Deliverables blob (FY25), keyed by indicator PK ---
        deliverables_blob = {}
        for ind_id, name, progress_clean, desc, src, media, std in DELIVERABLES:
            deliverables_blob[str(deliverables[ind_id].id)] = {
                "input_value": progress_category(progress_clean), "progress": "", "deliverable_quantity": "",
                "description": desc, "data_source": src, "next_steps": "",
                "supporting_materials_url": media,
            }
        add_field("deliverables", str(deliverables_blob))

        # --- Results indicators blob (FY25), keyed by indicator PK ---
        results_blob = {}
        for ind_id, name, unit, iv, base, tgt, datacol, std, level in RESULTS_INDICATORS:
            results_blob[str(results[ind_id].id)] = {
                "input_value": iv, "baseline_value": base, "year_baseline": None,
                "progress": "", "target_value": tgt, "year_target": None,
                "data_collection": datacol, "level_of_result": level,
            }
        add_field("custom_indicators", str(results_blob))

        session.commit()
    finally:
        session.close()

    print("Haiti example seeded from master dataset.")
    print(f"  Grant:        {GRANT_NUMBER} ({PCODE}) - {GRANT_DISPLAY}")
    print(f"  TTL login:    username={TTL_USERNAME}  password={TTL_PASSWORD}")
    print(f"  Fiscal years: {', '.join(FISCAL_YEARS)}  (report seeded under {TARGET_FY})")
    print(f"  Deliverables: {len(DELIVERABLES)}  |  Results indicators: {len(RESULTS_INDICATORS)}")


if __name__ == "__main__":
    main()
