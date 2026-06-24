"""Seed a richer dataset for manually testing the TTL reporting features.

Builds on the minimal seed (run seed_dev.py first, or this will create the
base rows too) and adds enough content to exercise the recent portal edits:

  * Three deliverable indicators (1 mandatory, 2 optional) mapped to the
    demo trust fund, each with an indicator_prompt set so the Outputs/
    deliverables page renders without error.
  * A saved FY25 report so the app auto-resolves the fiscal year and you
    land directly in a populated report (no "select a fiscal year" gate).
  * A deliverables blob with two filled mapped deliverables PLUS one active
    custom (TTL-added) deliverable and one archived custom deliverable, so
    the add / remove(archive) / restore flow has data on first load.
  * A partially filled Strategic Objective (the "Challenges" field only),
    so you can test "Save draft" (succeeds, lists what's missing) versus
    the primary "Save" (blocked until all mandatory fields are filled).
  * A few regions/countries so Basic Grant Information dropdowns work, plus
    basic grant fields for FY25.

Idempotent: re-running will not duplicate rows and will not overwrite
report content you have already edited in the app. SQLite local dev only:

    ./venv/Scripts/python.exe seed_test_data.py
"""
import datetime

from connection import create_session
from model import (
    Team, User, FiscalYear, TrustFund, Indicator, TrustFundIndicatorMapping,
    Region, Country, GrantInfo,
)

NOW = datetime.datetime.now()
TTL_USERNAME = "ttl_demo"
TTL_PASSWORD = "demo123"
TARGET_FY = "FY25"


def get_or_create(session, model, defaults=None, **filters):
    instance = session.query(model).filter_by(**filters).first()
    if instance:
        return instance, False
    params = {**filters, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    session.flush()  # assign PK without committing yet
    return instance, True


def upsert_grant_field(session, trustfund_id, fiscal_year_id, team_id, field, value):
    """Create a grant_info_long row only if that field doesn't exist yet.

    Never overwrites an existing value, so manual edits made in the app
    survive a re-run of this script.
    """
    existing = session.query(GrantInfo).filter_by(
        trustfund_id=trustfund_id, fiscal_year_id=fiscal_year_id,
        field=field, deleted=False,
    ).first()
    if existing:
        return existing
    row = GrantInfo(
        trustfund_id=trustfund_id, fiscal_year_id=fiscal_year_id,
        field=field, value=value, team_id=team_id, deleted=False,
        created_at=NOW, updated_at=NOW,
    )
    session.add(row)
    session.flush()
    return row


def main():
    session = create_session()
    try:
        team, _ = get_or_create(
            session, Team, team="Demo Team",
            defaults={"created_at": NOW, "updated_at": NOW},
        )

        get_or_create(
            session, User, username=TTL_USERNAME,
            defaults={"password": TTL_PASSWORD, "team_id": team.id,
                      "created_at": NOW, "updated_at": NOW},
        )

        fys = {}
        for fy_label in ("FY24", "FY25", "FY26"):
            fy, _ = get_or_create(
                session, FiscalYear, fy=fy_label,
                defaults={"created_at": NOW, "updated_at": NOW},
            )
            fys[fy_label] = fy

        trustfund, _ = get_or_create(
            session, TrustFund, name=TTL_USERNAME, team_id=team.id,
            defaults={"project_type": "Trust Fund",
                      "description": "Demo trust fund for local development",
                      "pcode": "P000000", "grant": "TF0A0000",
                      "ttl": "Demo TTL", "created_at": NOW, "updated_at": NOW},
        )

        # --- Reference data so Basic Grant Information dropdowns work --------
        regions = {}
        for label in ("AFR", "EAP", "LAC"):
            r, _ = get_or_create(
                session, Region, region=label,
                defaults={"created_at": NOW, "updated_at": NOW},
            )
            regions[label] = r
        for cname in ("Kenya", "Nigeria", "India", "Brazil"):
            get_or_create(
                session, Country, country=cname,
                defaults={"created_at": NOW, "updated_at": NOW},
            )

        # --- Deliverable indicators (mapped to the trust fund) --------------
        indicator_specs = [
            ("IND-001", "Number of beneficiaries reached", "Number", "Mandatory",
             "Total unique beneficiaries reached since grant activation."),
            ("IND-002", "Policy notes published", "Short Text", "Optional",
             "Short title or reference of each policy note produced."),
            ("IND-003", "Training workshops delivered", "Long Text", "Optional",
             "Describe the training workshops delivered this fiscal year."),
        ]
        indicators = {}
        for ind_id, name, unit, relation, definition in indicator_specs:
            ind, _ = get_or_create(
                session, Indicator, indicator_id=ind_id, team_id=team.id,
                defaults={"indicator_name": name,
                          "indicator_prompt": name,
                          "indicator_definition": definition,
                          "unit_of_measurement": unit,
                          "custom_indicator": False,
                          "created_at": NOW, "updated_at": NOW},
            )
            # Backfill prompt on any pre-existing row (avoids the deliverables
            # page calling .endswith() on a None prompt).
            if not ind.indicator_prompt:
                ind.indicator_prompt = name
            indicators[ind_id] = ind
            get_or_create(
                session, TrustFundIndicatorMapping,
                trustfund_id=trustfund.id, indicator_id=ind.id,
                defaults={"relation_ship": relation, "team_id": team.id,
                          "created_at": NOW, "updated_at": NOW},
            )

        # --- Results indicators (custom_indicator=True, mapped) -------------
        # The Results Indicators page renders indicators with custom_indicator
        # == True (the deliverables page uses == False), so these are separate
        # from the deliverable indicators above.
        ci_indicator_specs = [
            ("RI-001", "Increase in MSME lending volume (USD)", "Number", "Mandatory"),
            ("RI-002", "Share of women-led firms financed (%)", "Percentage", "Optional"),
        ]
        ci_indicators = {}
        for ind_id, name, unit, relation in ci_indicator_specs:
            ind, _ = get_or_create(
                session, Indicator, indicator_id=ind_id, team_id=team.id,
                defaults={"indicator_name": name,
                          "indicator_prompt": name,
                          "unit_of_measurement": unit,
                          "custom_indicator": True,
                          "created_at": NOW, "updated_at": NOW},
            )
            if not ind.indicator_prompt:
                ind.indicator_prompt = name
            ci_indicators[ind_id] = ind
            get_or_create(
                session, TrustFundIndicatorMapping,
                trustfund_id=trustfund.id, indicator_id=ind.id,
                defaults={"relation_ship": relation, "team_id": team.id,
                          "created_at": NOW, "updated_at": NOW},
            )

        session.flush()  # ensure indicator PKs are assigned before keying blob

        fy25 = fys[TARGET_FY]

        # --- Basic grant information (FY25) ---------------------------------
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "p_code_instrument", "ASA")
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "country", "Kenya, Nigeria")
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "f4d_association",
                           "Yes, this P code is used solely for F4D funded activities")
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "region_id", str(regions["AFR"].id))
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "pillars", "Pillar 2: Financing the Poor and Vulnerable")

        # --- Strategic objective (partial, for draft testing) ---------------
        # Only "challenges" is filled; strategic_objective and overall_progress
        # (both mandatory) are intentionally left blank.
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "challenges",
                           "Limited access to affordable finance for rural MSMEs.")

        # --- Deliverables blob (FY25) ---------------------------------------
        # Keyed by indicator PK (as string) for mapped deliverables, plus
        # custom_* keys for TTL-added ones. Matches what the app serializes.
        deliverables_blob = {
            str(indicators["IND-001"].id): {
                "input_value": 1500,
                "progress": "3",
                "deliverable_quantity": "2",
                "description": "Beneficiaries reached across three program cohorts.",
                "data_source": "Program M&E tracker",
                "next_steps": "Expand outreach to two additional districts.",
                "supporting_materials_url": "",
            },
            str(indicators["IND-002"].id): {
                "input_value": "Note on MSME credit guarantees",
                "progress": "1",
                "deliverable_quantity": "1",
                "description": "Policy note shared with the central bank.",
                "data_source": "",
                "next_steps": "",
                "supporting_materials_url": "",
            },
            "custom_demo0001": {
                "name": "Stakeholder workshop series",
                "custom": True,
                "archived": False,
                "input_value": "Three regional workshops with 120 participants.",
                "progress": "3",
                "deliverable_quantity": "3",
                "description": "Workshops held in Q2-Q3 with local financial institutions.",
                "data_source": "Attendance sheets",
                "next_steps": "Publish a synthesis brief.",
                "supporting_materials_url": "",
            },
            "custom_demo0002": {
                "name": "Pilot dashboard (archived example)",
                "custom": True,
                "archived": True,
                "input_value": "Prototype dropped in favor of the central portal.",
                "progress": "",
                "deliverable_quantity": "",
                "description": "",
                "data_source": "",
                "next_steps": "",
                "supporting_materials_url": "",
            },
        }
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "deliverables", str(deliverables_blob))

        # --- Results indicators blob (FY25) ---------------------------------
        # Keyed by indicator PK (as string) for mapped indicators, plus
        # custom_* keys for TTL-added ones (one active, one archived).
        custom_indicators_blob = {
            str(ci_indicators["RI-001"].id): {
                "input_value": 4200000,
                "baseline_value": "1000000",
                "year_baseline": 2023,
                "progress": "Lending volume grew across two partner banks.",
                "target_value": "5000000",
                "year_target": 2026,
                "data_collection": "Partner bank quarterly reports (ISR).",
                "level_of_result": "Outcome",
            },
            str(ci_indicators["RI-002"].id): {
                "input_value": 35,
                "baseline_value": "20",
                "year_baseline": 2023,
                "progress": "Share of women-led firms financed rose to 35%.",
                "target_value": "50",
                "year_target": 2026,
                "data_collection": "Program M&E tracker.",
                "level_of_result": "Intermediate Outcome",
            },
            "custom_ri000001": {
                "name": "Digital payments adoption rate",
                "custom": True,
                "archived": False,
                "level_of_result": "Output",
                "input_value": "28% of beneficiaries adopted digital payments.",
                "baseline_value": "10",
                "year_baseline": 2023,
                "progress": "Adoption tracked via mobile money partner data.",
                "target_value": "40",
                "year_target": 2026,
                "data_collection": "Mobile money provider dashboards.",
            },
            "custom_ri000002": {
                "name": "Legacy KPI (archived example)",
                "custom": True,
                "archived": True,
                "level_of_result": None,
                "input_value": "Retired in favor of the lending-volume outcome.",
                "baseline_value": "",
                "year_baseline": None,
                "progress": "",
                "target_value": "",
                "year_target": None,
                "data_collection": "",
            },
        }
        upsert_grant_field(session, trustfund.id, fy25.id, team.id,
                           "custom_indicators", str(custom_indicators_blob))

        session.commit()
    finally:
        session.close()

    print("Test data seeded.")
    print(f"  TTL login:    username={TTL_USERNAME}  password={TTL_PASSWORD}")
    print(f"  Report:       {TARGET_FY} (auto-resolves on login)")
    print("  Deliverables: 2 mapped (filled) + 1 custom active + 1 custom archived")
    print("  Indicators:   2 mapped (filled) + 1 custom active + 1 custom archived")
    print("  Strategic:    'Challenges' filled; 2 mandatory fields blank (test Save draft)")
    print("  To test:      Report new results -> Outputs/deliverables and Results Indicators")


if __name__ == "__main__":
    main()
