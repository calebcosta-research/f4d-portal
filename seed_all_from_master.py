"""Bulk-load ALL trust funds from F4D_rd_master.xlsx into the database.

For each Trust Fund Number it creates:
  * a Team, a User (username=<TFnum>_admin, password=<TFnum>_p), and a
    TrustFund (name == username so the app resolves the report; grant == TFnum).
  * Indicators for its deliverables (Categorical) and results (typed), mapped
    Mandatory, plus a filled FY25 report (basic info, objective, deliverable
    and results blobs).

Per-trust-fund clean rebuild, so re-running reproduces the master exactly.
Reads the master path from env F4D_MASTER (default: the OneDrive copy).

Run with the same DB env vars as the app, e.g. against Azure Postgres:
  db_backend=postgres sql_host=... sql_username=... sql_password=... \
  sql_database=f4d sql_port=5432 db_schema= ./venv/Scripts/python.exe seed_all_from_master.py
"""
import datetime
import os

import pandas as pd

from connection import create_session
from model import (
    Team, User, FiscalYear, TrustFund, Indicator, TrustFundIndicatorMapping,
    Region, Country, GrantInfo,
)

MASTER = os.environ.get(
    "F4D_MASTER", r"C:\Users\caleb\OneDrive\Documents\F4D_rd_master.xlsx")
NOW = datetime.datetime.now()
TARGET_FY = "FY25"
FISCAL_YEARS = ("FY24", "FY25", "FY26")
CATS = "Completed, In Progress, Not Started"
DELIV_CATS = ("Completed", "In Progress", "Not Started")
F4D_ASSOC = "Yes, this P code is used solely for F4D funded activities"

PILLAR_NAMES = {
    "pillar 1": "Pillar 1: Strengthening Financial Sector Resiliency",
    "pillar 2": "Pillar 2: Financing the Poor and Vulnerable",
    "pillar 3": "Pillar 3: Financing the Real Economy",
    "pillar 4": "Pillar 4: Developing Financial Markets",
}


def norm(v):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return str(v).strip()


def to_float(v):
    try:
        return float(norm(v).replace(",", "").replace("$", "").replace("%", ""))
    except (ValueError, AttributeError):
        return None


def progress_category(v):
    """Map Progress_clean onto the 3 deliverable categories; else '' (blank)."""
    v = norm(v)
    if v.lower() in ("complete", "completed"):
        return "Completed"
    if v in DELIV_CATS:
        return v
    return ""


def results_unit_value(unit, raw):
    """Pick a safe unit_of_measurement + input_value for a results indicator.

    Only use the numeric widgets when the value really parses to a number,
    otherwise fall back to Short Text so the page never errors on bad data.
    """
    u = norm(unit).lower()
    f = to_float(raw)
    if u in ("number", "us$", "count") and f is not None:
        return "Number", f
    if "percent" in u and f is not None:
        return "Percentage", f
    return "Short Text", norm(raw)


def find_col(cols, *subs):
    for c in cols:
        cl = str(c).lower()
        if all(s.lower() in cl for s in subs):
            return c
    return None


def main():
    deliv = pd.read_excel(MASTER, sheet_name="Deliverables", dtype=str)
    res = pd.read_excel(MASTER, sheet_name="Results", dtype=str)
    dcols, rcols = list(deliv.columns), list(res.columns)

    # Resolve column names (robust to case / nbsp / long headers).
    D = {
        "tf": "Trust Fund Number", "name": "Deliverable name",
        "prog": "Progress_clean", "desc": find_col(dcols, "brief description"),
        "src": "Data source", "media": find_col(dcols, "photos"),
        "pub": find_col(dcols, "publicly available"), "std": "standard_indicator",
    }
    R = {
        "tf": "Trust Fund Number", "name": "Indicator name",
        "unit": "Unit of measure", "prog": "Progress_clean",
        "base": find_col(rcols, "baseline value"),
        "target": find_col(rcols, "target value"),
        "how": find_col(rcols, "how are you collecting"), "std": "standard_indicator",
    }
    META = {
        "pcode": find_col(dcols, "project pcode") or find_col(dcols, "pcode"),
        "region": "Region", "country": "Country",
        "title": find_col(dcols, "project title"),
        "ttl": find_col(dcols, "f4d ttl name"), "objective": "Objective",
        "grant": "Grant Name",
    }
    PILLAR_COLS = {k: find_col(dcols, k) for k in PILLAR_NAMES}
    THEME_COLS = {
        "Climate change and sustainable finance": find_col(dcols, "climate change"),
        "Advancing digitalization": find_col(dcols, "digital financial"),
        "Financing solutions to close gender gaps": find_col(dcols, "gender"),
    }

    def tf_key(s):
        return norm(s)

    deliv["_tf"] = deliv[D["tf"]].map(tf_key)
    res["_tf"] = res[R["tf"]].map(tf_key)
    all_tfs = sorted(t for t in set(deliv["_tf"]) | set(res["_tf"]) if t)

    session = create_session()
    fys = {}
    for label in FISCAL_YEARS:
        fy = session.query(FiscalYear).filter_by(fy=label).first()
        if not fy:
            fy = FiscalYear(fy=label, created_at=NOW, updated_at=NOW)
            session.add(fy); session.flush()
        fys[label] = fy
    fy25 = fys[TARGET_FY]

    region_cache = {}
    def region_id(name):
        n = norm(name).title()
        if not n:
            return None
        if n not in region_cache:
            r = session.query(Region).filter_by(region=n).first()
            if not r:
                r = Region(region=n, created_at=NOW, updated_at=NOW)
                session.add(r); session.flush()
            region_cache[n] = r.id
        return region_cache[n]

    loaded, errors = 0, []
    for tfnum in all_tfs:
        try:
            drows = deliv[deliv["_tf"] == tfnum]
            rrows = res[res["_tf"] == tfnum]
            meta = (drows.iloc[0] if len(drows) else rrows.iloc[0])

            username = f"{tfnum}_admin"
            team = session.query(Team).filter_by(team=f"Team {tfnum}").first()
            if not team:
                team = Team(team=f"Team {tfnum}", created_at=NOW, updated_at=NOW)
                session.add(team); session.flush()
            if not session.query(User).filter_by(username=username).first():
                session.add(User(username=username, password=f"{tfnum}_p",
                                 team_id=team.id, created_at=NOW, updated_at=NOW))
            tf = session.query(TrustFund).filter_by(name=username).first()
            if not tf:
                tf = TrustFund(name=username, project_type="Trust Fund",
                               team_id=team.id, created_at=NOW, updated_at=NOW)
                session.add(tf); session.flush()
            tf.grant = tfnum
            tf.pcode = norm(meta.get(META["pcode"]))
            tf.description = norm(meta.get(META["title"])) or norm(meta.get(META["grant"]))
            tf.ttl = norm(meta.get(META["ttl"]))
            tf.updated_at = NOW

            # Clean rebuild of this grant's content.
            session.flush()
            session.query(GrantInfo).filter_by(trustfund_id=tf.id).delete(synchronize_session=False)
            session.query(TrustFundIndicatorMapping).filter_by(trustfund_id=tf.id).delete(synchronize_session=False)
            session.query(Indicator).filter_by(team_id=team.id).delete(synchronize_session=False)
            session.flush()

            def add_ind(ind_id, name, prompt, unit, std, custom, categorical=None):
                ind = Indicator(indicator_id=ind_id, indicator_name=name or ind_id,
                                indicator_prompt=prompt or "Progress Update",
                                unit_of_measurement=unit, categorical_unit=categorical,
                                standard_indicator_name=std or None, custom_indicator=custom,
                                team_id=team.id, created_at=NOW, updated_at=NOW)
                session.add(ind); session.flush()
                session.add(TrustFundIndicatorMapping(
                    trustfund_id=tf.id, indicator_id=ind.id, relation_ship="Mandatory",
                    team_id=team.id, created_at=NOW, updated_at=NOW))
                return ind

            # Deliverables
            deliv_blob = {}
            i = 0
            for _, row in drows.iterrows():
                dname = norm(row.get(D["name"]))
                if not dname:
                    continue
                i += 1
                ind = add_ind(f"{tfnum}-D{i}", dname, "Progress Update", "Categorical",
                              norm(row.get(D["std"])), False, categorical=CATS)
                has_media = "Yes" if (norm(row.get(D["media"])) or norm(row.get(D["pub"]))) else "No"
                deliv_blob[str(ind.id)] = {
                    "input_value": progress_category(row.get(D["prog"])),
                    "progress": "", "deliverable_quantity": "",
                    "description": norm(row.get(D["desc"])),
                    "data_source": norm(row.get(D["src"])),
                    "next_steps": "", "supporting_materials_url": has_media,
                }

            # Results indicators
            res_blob = {}
            j = 0
            for _, row in rrows.iterrows():
                rname = norm(row.get(R["name"]))
                if not rname:
                    continue
                j += 1
                unit, ival = results_unit_value(row.get(R["unit"]), row.get(R["prog"]))
                ind = add_ind(f"{tfnum}-RI{j}", rname, rname, unit,
                              norm(row.get(R["std"])), True)
                res_blob[str(ind.id)] = {
                    "input_value": ival, "baseline_value": norm(row.get(R["base"])),
                    "year_baseline": None, "progress": "",
                    "target_value": norm(row.get(R["target"])), "year_target": None,
                    "data_collection": norm(row.get(R["how"])), "level_of_result": "Output",
                }

            # Basic grant info + objective (FY25)
            def addf(field, value):
                if value:
                    session.add(GrantInfo(trustfund_id=tf.id, fiscal_year_id=fy25.id,
                                          field=field, value=value, team_id=team.id,
                                          deleted=False, created_at=NOW, updated_at=NOW))
            country = norm(meta.get(META["country"]))
            if country:
                session.query(Country).filter_by(country=country).first() or \
                    session.add(Country(country=country, created_at=NOW, updated_at=NOW))
            addf("country", country)
            addf("region_id", str(region_id(meta.get(META["region"])) or "") or None)
            addf("f4d_association", F4D_ASSOC)
            pillars = [PILLAR_NAMES[k] for k, c in PILLAR_COLS.items()
                       if c and norm(meta.get(c)) in ("1", "1.0", "yes", "y")]
            addf("pillars", ", ".join(pillars))
            ccts = [name for name, c in THEME_COLS.items()
                    if c and norm(meta.get(c)) in ("1", "1.0", "yes", "y")]
            addf("ccts", ", ".join(ccts))
            addf("strategic_objective", norm(meta.get(META["objective"])))
            if deliv_blob:
                addf("deliverables", str(deliv_blob))
            if res_blob:
                addf("custom_indicators", str(res_blob))

            session.commit()
            loaded += 1
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            errors.append((tfnum, str(exc)[:160]))

    session.close()
    print(f"Loaded {loaded}/{len(all_tfs)} trust funds.")
    print("Login scheme: username=<TFnum>_admin  password=<TFnum>_p")
    if errors:
        print(f"{len(errors)} errors:")
        for t, e in errors[:15]:
            print(f"  {t}: {e}")


if __name__ == "__main__":
    main()
