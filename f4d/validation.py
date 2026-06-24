"""Whole-report mandatory-field validation, shared by the Review & Submit page.

Reads only *persisted* data from grant_info_long (not live widget state), so it
reflects what the TTL has actually Saved. Each section's rules mirror the
per-section checks in f4d/sections/*: Basic Grant Information, Strategic
Objective, Collaboration use fixed mandatory fields; Deliverables and Results
Indicators require a value for every Mandatory-mapped indicator. Lending
Operations has no mandatory fields.

Pure module (no Streamlit) so it can be unit-tested headlessly.
"""

import ast

from model import GrantInfo, Indicator, TrustFundIndicatorMapping


def _get(session, tf_id, fy_id, field):
    row = (
        session.query(GrantInfo)
        .filter_by(trustfund_id=tf_id, fiscal_year_id=fy_id, field=field, deleted=False)
        .first()
    )
    return row.value if row else None


def _get_blob(session, tf_id, fy_id, field):
    raw = _get(session, tf_id, fy_id, field)
    if not raw:
        return {}
    try:
        data = ast.literal_eval(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, SyntaxError):
        return {}


def _empty(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _empty_collection(value):
    if _empty(value):
        return True
    return str(value).strip() in ("[]", "{}", "''", '""')


def _missing_mandatory_mapped(session, tf_id, fy_id, blob_field, custom_indicator):
    """Missing indicator names for Mandatory mappings without a saved value."""
    blob = _get_blob(session, tf_id, fy_id, blob_field)
    mappings = (
        session.query(TrustFundIndicatorMapping)
        .filter(TrustFundIndicatorMapping.trustfund_id == tf_id)
        .all()
    )
    missing = []
    for mapping in mappings:
        if mapping.relation_ship != "Mandatory":
            continue
        indicator = (
            session.query(Indicator)
            .filter(Indicator.id == mapping.indicator_id,
                    Indicator.custom_indicator == custom_indicator)
            .first()
        )
        if not indicator:
            continue
        entry = blob.get(str(mapping.indicator_id), {})
        if not isinstance(entry, dict) or entry.get("archived"):
            continue
        iv = entry.get("input_value")
        if iv is None or iv == "" or (isinstance(iv, (int, float)) and iv < 0):
            missing.append(indicator.indicator_name)
    return missing


# Section -> list of (persisted field name, human label) for the fixed-field sections.
_FIXED_RULES = {
    "Basic Grant Information": [
        ("p_code_instrument", "Product line/instrument"),
        ("f4d_association", "F4D Association"),
        ("region_id", "Region"),
        ("country", "Country"),
        ("pillars", "Pillars"),
    ],
    "Strategic Objective & Progress": [
        ("challenges", "Challenges the grant is going to address"),
        ("strategic_objective", "Grant's strategic objective"),
        ("overall_progress", "Overall progress since inception"),
    ],
}


def validate_report(session, tf_id, fy_id):
    """Return {section_name: [missing item labels]} across the whole report.

    A section maps to an empty list when complete. Section order matches the
    report's subpage order so the summary reads top-to-bottom.
    """
    results = {}

    for section, rules in _FIXED_RULES.items():
        results[section] = [
            label for field, label in rules if _empty(_get(session, tf_id, fy_id, field))
        ]

    # Collaboration: must answer the Yes/No question; if "Yes", at least one
    # collaboration detail entry is required.
    collab_missing = []
    answer = (_get(session, tf_id, fy_id, "collaborations") or "").strip()
    if not answer:
        collab_missing.append("Collaboration/partnership question")
    elif answer == "Yes":
        fields = session.query(GrantInfo.field).filter(
            GrantInfo.trustfund_id == tf_id,
            GrantInfo.fiscal_year_id == fy_id,
            GrantInfo.deleted == False,
        ).all()
        if not any(f[0].startswith("collaboration_") for f in fields):
            collab_missing.append("At least one collaboration detail")
    results["Collaboration/Partnership"] = collab_missing

    results["Outputs/deliverables"] = _missing_mandatory_mapped(
        session, tf_id, fy_id, "deliverables", custom_indicator=False)
    results["Results Indicators"] = _missing_mandatory_mapped(
        session, tf_id, fy_id, "custom_indicators", custom_indicator=True)

    return results


def report_is_complete(results):
    """True when no section has missing items."""
    return all(not missing for missing in results.values())
