"""Seed a polished FAKE trust fund for the demo, with TWO years of data.

Creates TFDEMO01 (login TFDEMO01_admin / TFDEMO01_p) with complete FY24 AND FY25
reports, so the "Previous Fiscal Year" panels populate (view FY25 -> FY24 shows;
view FY26 -> FY25 shows). Fully fictional content.

Clean rebuild (safe to re-run). Delete it afterwards with:
    ./venv/Scripts/python.exe seed_demo_fund.py --delete

Run against Azure Postgres with the app's DB env vars set.
"""
import datetime
import sys

from connection import create_session
from model import (
    Team, User, FiscalYear, TrustFund, Indicator, TrustFundIndicatorMapping,
    Region, Country, GrantInfo,
)

NOW = datetime.datetime.now()
TFNUM = "TFDEMO01"
USERNAME = f"{TFNUM}_admin"
PASSWORD = f"{TFNUM}_p"
TEAM = "Demo Fund Team"
GRANT_DISPLAY = "Financial Inclusion Demonstration Fund (DEMO)"
TTL_NAMES = "Jane Demo; John Sample"
REGION = "Africa"
COUNTRY = "Kenya"
CATS = "Completed, In Progress, Not Started"

DELIVERABLES = [
    ("TFDEMO01-D1", "Mobile money agent network expansion plan",
     "Number of beneficiary countries supported to improve financial "
     "infrastructures for payments and digital financial services"),
    ("TFDEMO01-D2", "Financial consumer protection regulation inputs drafted",
     "Number of laws, regulations supported."),
    ("TFDEMO01-D3", "Digital financial literacy curriculum",
     "Number of beneficiary countries supported with financial education initiatives"),
]
RESULTS = [
    ("TFDEMO01-RI1", "Number of new digital transaction accounts opened", "Number"),
    ("TFDEMO01-RI2", "Share of adults with a transaction account", "Percentage"),
]

# Per-year report content. Keyed by FY label.
YEARS = {
    "FY24": {
        "strategic_objective": "Expand access to and usage of digital financial "
                               "services for underserved households and MSMEs.",
        "overall_progress": "Foundational activities launched; agent mapping and "
                            "baseline survey completed.",
        "challenges": "Limited rural connectivity and low initial trust in digital channels.",
        "deliverables": {
            "TFDEMO01-D1": ("In Progress", "2", "1", "Initial agent-network mapping underway.", "No"),
            "TFDEMO01-D2": ("Not Started", "1", "0", "Scoping the regulatory gap analysis.", "No"),
            "TFDEMO01-D3": ("In Progress", "3", "1", "Curriculum outline drafted.", "Yes"),
        },
        "results": {
            "TFDEMO01-RI1": (120000, "0", "500000", "Initial rollout in the capital region."),
            "TFDEMO01-RI2": (42, "38", "60", "Baseline survey completed."),
        },
    },
    "FY25": {
        "strategic_objective": "Expand access to and usage of digital financial "
                               "services for underserved households and MSMEs.",
        "overall_progress": "Adoption accelerated across three regions; consumer "
                            "protection regulation drafted and under review.",
        "challenges": "Sustaining agent liquidity in remote areas remains a constraint.",
        "deliverables": {
            "TFDEMO01-D1": ("Completed", "2", "2", "Agent network expanded to two regions.", "Yes"),
            "TFDEMO01-D2": ("In Progress", "1", "0", "Draft regulation submitted for review.", "Yes"),
            "TFDEMO01-D3": ("Completed", "3", "3", "Curriculum delivered to three cohorts.", "Yes"),
        },
        "results": {
            "TFDEMO01-RI1": (310000, "0", "500000", "Adoption accelerated across three regions."),
            "TFDEMO01-RI2": (51, "38", "60", "Account ownership rising toward target."),
        },
    },
}


def _delete(session):
    tf = session.query(TrustFund).filter_by(name=USERNAME).first()
    team = session.query(Team).filter_by(team=TEAM).first()
    if tf:
        session.query(GrantInfo).filter_by(trustfund_id=tf.id).delete(synchronize_session=False)
        session.query(TrustFundIndicatorMapping).filter_by(trustfund_id=tf.id).delete(synchronize_session=False)
    if team:
        session.query(Indicator).filter_by(team_id=team.id).delete(synchronize_session=False)
    if tf:
        session.query(TrustFund).filter_by(id=tf.id).delete(synchronize_session=False)
    session.query(User).filter_by(username=USERNAME).delete(synchronize_session=False)
    if team:
        session.query(Team).filter_by(id=team.id).delete(synchronize_session=False)
    session.commit()
    print(f"Deleted demo fund {TFNUM} and its data.")


def main():
    session = create_session()
    try:
        if "--delete" in sys.argv:
            _delete(session)
            return

        team = session.query(Team).filter_by(team=TEAM).first() or \
            Team(team=TEAM, created_at=NOW, updated_at=NOW)
        if not team.id:
            session.add(team); session.flush()
        if not session.query(User).filter_by(username=USERNAME).first():
            session.add(User(username=USERNAME, password=PASSWORD, team_id=team.id,
                             created_at=NOW, updated_at=NOW))

        fys = {}
        for label in ("FY24", "FY25", "FY26"):
            fy = session.query(FiscalYear).filter_by(fy=label).first() or \
                FiscalYear(fy=label, created_at=NOW, updated_at=NOW)
            if not fy.id:
                session.add(fy); session.flush()
            fys[label] = fy

        region = session.query(Region).filter_by(region=REGION).first() or \
            Region(region=REGION, created_at=NOW, updated_at=NOW)
        if not region.id:
            session.add(region); session.flush()
        if not session.query(Country).filter_by(country=COUNTRY).first():
            session.add(Country(country=COUNTRY, created_at=NOW, updated_at=NOW))

        tf = session.query(TrustFund).filter_by(name=USERNAME).first() or \
            TrustFund(name=USERNAME, project_type="Trust Fund", team_id=team.id,
                      created_at=NOW, updated_at=NOW)
        if not tf.id:
            session.add(tf); session.flush()
        tf.grant = TFNUM
        tf.pcode = "P999999"
        tf.description = GRANT_DISPLAY
        tf.ttl = TTL_NAMES
        tf.updated_at = NOW

        # Clean rebuild of this grant's content.
        session.flush()
        session.query(GrantInfo).filter_by(trustfund_id=tf.id).delete(synchronize_session=False)
        session.query(TrustFundIndicatorMapping).filter_by(trustfund_id=tf.id).delete(synchronize_session=False)
        session.query(Indicator).filter_by(team_id=team.id).delete(synchronize_session=False)
        session.flush()

        def add_ind(ind_id, name, prompt, unit, std, custom, categorical=None):
            ind = Indicator(indicator_id=ind_id, indicator_name=name, indicator_prompt=prompt,
                            unit_of_measurement=unit, categorical_unit=categorical,
                            standard_indicator_name=std, custom_indicator=custom,
                            team_id=team.id, created_at=NOW, updated_at=NOW)
            session.add(ind); session.flush()
            session.add(TrustFundIndicatorMapping(
                trustfund_id=tf.id, indicator_id=ind.id, relation_ship="Mandatory",
                team_id=team.id, created_at=NOW, updated_at=NOW))
            return ind

        deliv = {d[0]: add_ind(d[0], d[1], "Progress Update", "Categorical", d[2], False, CATS)
                 for d in DELIVERABLES}
        res = {r[0]: add_ind(r[0], r[1], r[1], r[2], None, True) for r in RESULTS}
        session.flush()

        def addf(fy, field, value):
            session.add(GrantInfo(trustfund_id=tf.id, fiscal_year_id=fy.id, field=field,
                                  value=value, team_id=team.id, deleted=False,
                                  created_at=NOW, updated_at=NOW))

        for label, data in YEARS.items():
            fy = fys[label]
            addf(fy, "p_code_instrument", "ASA")
            addf(fy, "country", COUNTRY)
            addf(fy, "f4d_association", "Yes, this P code is used solely for F4D funded activities")
            addf(fy, "region_id", str(region.id))
            addf(fy, "pillars", "Pillar 2: Financing the Poor and Vulnerable")
            addf(fy, "ccts", "Advancing digitalization")
            addf(fy, "strategic_objective", data["strategic_objective"])
            addf(fy, "overall_progress", data["overall_progress"])
            addf(fy, "challenges", data["challenges"])
            # Collaboration: Yes + one detail entry.
            addf(fy, "collaborations", "Yes")
            addf(fy, "collaboration_1", str({
                "type": "Other World Bank teams (e.g. GPs)",
                "partner_detail": "Digital Development GP",
                "describe": "Joint design of the agent-network and connectivity components.",
                "lessons_learned": "Early alignment on shared KPIs sped up delivery.",
            }))
            deliv_blob = {}
            for ind_id, (status, target, qty, desc, media) in data["deliverables"].items():
                deliv_blob[str(deliv[ind_id].id)] = {
                    "input_value": status, "progress": target, "deliverable_quantity": qty,
                    "description": desc, "data_source": "Program M&E tracker",
                    "next_steps": "", "supporting_materials_url": media,
                }
            addf(fy, "deliverables", str(deliv_blob))
            res_blob = {}
            for ind_id, (val, base, tgt, prog) in data["results"].items():
                res_blob[str(res[ind_id].id)] = {
                    "input_value": val, "baseline_value": base, "year_baseline": 2023,
                    "progress": prog, "target_value": tgt, "year_target": 2026,
                    "data_collection": "National survey / provider MIS", "level_of_result": "Outcome",
                }
            addf(fy, "custom_indicators", str(res_blob))

        session.commit()
    finally:
        session.close()

    print("Demo fund seeded.")
    print(f"  Login:        {USERNAME} / {PASSWORD}")
    print(f"  Grant:        {TFNUM} - {GRANT_DISPLAY}")
    print(f"  Years:        FY24 + FY25 complete (view FY25 -> FY24 shows as previous; FY26 -> FY25)")


if __name__ == "__main__":
    main()
