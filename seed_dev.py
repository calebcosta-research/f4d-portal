"""Seed the local development database with a minimal, working dataset.

Creates one team, a TTL login, two fiscal years, a trust fund (named to
match the TTL username, which is how the app resolves a user's report
context), and one indicator mapped to that trust fund so the
deliverables / results-indicator sections have content to show.

Idempotent: re-running it will not duplicate rows. Intended for SQLite
local development only (run with db_backend=sqlite). Usage:

    ./venv/Scripts/python.exe seed_dev.py
"""
import datetime

from connection import create_session
from model import (
    Team, User, FiscalYear, TrustFund, Indicator, TrustFundIndicatorMapping,
)

NOW = datetime.datetime.now()
TTL_USERNAME = "ttl_demo"
TTL_PASSWORD = "demo123"


def get_or_create(session, model, defaults=None, **filters):
    instance = session.query(model).filter_by(**filters).first()
    if instance:
        return instance, False
    params = {**filters, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    session.flush()  # assign PK without committing yet
    return instance, True


def main():
    session = create_session()
    try:
        team, _ = get_or_create(
            session, Team, team="Demo Team",
            defaults={"created_at": NOW, "updated_at": NOW},
        )

        user, _ = get_or_create(
            session, User, username=TTL_USERNAME,
            defaults={"password": TTL_PASSWORD, "team_id": team.id,
                      "created_at": NOW, "updated_at": NOW},
        )

        fy_objs = []
        for fy_label in ("FY24", "FY25"):
            fy, _ = get_or_create(
                session, FiscalYear, fy=fy_label,
                defaults={"created_at": NOW, "updated_at": NOW},
            )
            fy_objs.append(fy)

        # Trust fund name MUST equal the TTL username for the report context
        # to resolve (see f4d/context.py:_resolve_grant_context).
        trustfund, _ = get_or_create(
            session, TrustFund, name=TTL_USERNAME, team_id=team.id,
            defaults={"project_type": "Trust Fund",
                      "description": "Demo trust fund for local development",
                      "pcode": "P000000", "grant": "TF0A0000",
                      "ttl": "Demo TTL", "created_at": NOW, "updated_at": NOW},
        )

        indicator, _ = get_or_create(
            session, Indicator, indicator_id="IND-001", team_id=team.id,
            defaults={"indicator_name": "Number of beneficiaries reached",
                      "unit_of_measurement": "Number",
                      "custom_indicator": False,
                      "created_at": NOW, "updated_at": NOW},
        )

        get_or_create(
            session, TrustFundIndicatorMapping,
            trustfund_id=trustfund.id, indicator_id=indicator.id,
            defaults={"relation_ship": "Mandatory", "team_id": team.id,
                      "created_at": NOW, "updated_at": NOW},
        )

        session.commit()
    finally:
        session.close()

    print("Seed complete.")
    print(f"  Team:        Demo Team")
    print(f"  TTL login:   username={TTL_USERNAME}  password={TTL_PASSWORD}")
    print(f"  Trust fund:  {TTL_USERNAME}  (FY24, FY25)")
    print(f"  Indicator:   IND-001 (mandatory) mapped to the trust fund")


if __name__ == "__main__":
    main()
