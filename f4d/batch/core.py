"""Batch-import engine: parse -> validate -> map -> write.

Headless on purpose: this module imports no Streamlit, so it runs from the
command line (one-time migration) and is unit-testable. The in-app upload page
calls the same :func:`import_rows` with a live session.

Storage contract (must match the live app exactly):
  * One submission row == one (trust fund, fiscal year) pair.
  * Each non-empty field becomes a row in ``grant_info_long``:
    ``(trustfund_id, fiscal_year_id, field, value)``.
  * Value encoding mirrors what edit_results.py / the sections write:
      - text fields  -> the raw string
      - list fields  -> comma-joined string (the cell is taken as-is)
      - region_id    -> the integer id as a string
      - blob fields  -> ``str(obj)`` of a Python dict/list (NOT json), because
        the app reads these back with ast.literal_eval / eval. We re-encode
        through repr() so a cell containing JSON or a Python literal both work.

Nothing is written for empty cells, so re-running the importer is idempotent
and a partial sheet only updates the columns it actually fills in.
"""

import ast
import datetime
import json
from dataclasses import dataclass, field as dc_field

from model import GrantInfo, TrustFund, FiscalYear


# --- Field registry -------------------------------------------------------
#
# The canonical set of submission fields, with how each is stored. Derived from
# the live writers (f4d/edit_results.py ~line 1042, f4d/sections/*, exports.py).
# "kind" controls encoding only; every value lands in grant_info_long.value.

TEXT = "text"     # raw string
LIST = "list"     # comma-separated string, stored as given
INT = "int"       # integer id, stored as str
BLOB = "blob"     # python dict/list, stored as str(obj)

FIELD_KINDS = {
    # 1. Basic grant info
    "country": LIST,
    "p_code_instrument": TEXT,
    "p_code_description": TEXT,
    "f4d_association": TEXT,
    "region_id": INT,
    "pillars": LIST,
    "ccts": LIST,
    "pillar_explanations": BLOB,
    "cct_explanations": BLOB,
    # 2. Strategic objective & progress
    "challenges": TEXT,
    "strategic_objective": TEXT,
    "overall_progress": TEXT,
    "implementation_challenges": TEXT,
    "public_communication_external": TEXT,
    "public_communication_internal": TEXT,
    # 3. Lending operations
    "operations": BLOB,
    "cpfs": BLOB,
    # 4. Collaboration / partnership
    "collaborations": BLOB,
    "other_teams": TEXT,
    "other_ifis": TEXT,
    "other_orgs": TEXT,
    "describe_collaboration": TEXT,
    "lessons_learned": TEXT,
    # 5. Deliverables
    "deliverables": BLOB,
    # 6. Indicators
    "indicators": BLOB,
    "custom_indicators": BLOB,
}

# Columns that identify the row rather than carry a field value.
TRUSTFUND_COLUMN = "trust_fund"     # matched against TrustFund.name / pcode / grant
FISCAL_YEAR_COLUMN = "fiscal_year"  # matched against FiscalYear.fy
ID_COLUMNS = {TRUSTFUND_COLUMN, FISCAL_YEAR_COLUMN}


def _is_empty(value):
    """True for None, NaN, and blank/whitespace-only strings."""
    if value is None:
        return True
    # pandas NaN is a float that is not equal to itself.
    if isinstance(value, float) and value != value:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def encode_value(field_name, raw):
    """Encode a raw cell value into the string the app stores for this field.

    Raises ValueError with a human-readable message on bad input so the caller
    can attach it to the row's error report.
    """
    kind = FIELD_KINDS.get(field_name, TEXT)

    if kind == TEXT or kind == LIST:
        # LIST is stored exactly as typed (comma-separated); we don't reorder.
        return str(raw).strip()

    if kind == INT:
        try:
            return str(int(float(raw)))  # tolerates "12" and 12.0
        except (TypeError, ValueError):
            raise ValueError(f"{field_name!r} must be an integer id, got {raw!r}")

    if kind == BLOB:
        # Accept a dict/list directly, or a string holding JSON or a Python
        # literal. Re-encode via str(obj) to match the app's ast.literal_eval
        # readers. (When the security pass moves the app to JSON, change this
        # one place to json.dumps and the readers together.)
        if isinstance(raw, (dict, list)):
            obj = raw
        else:
            text = str(raw).strip()
            obj = None
            for parser in (json.loads, ast.literal_eval):
                try:
                    obj = parser(text)
                    break
                except (ValueError, SyntaxError):
                    continue
            if obj is None:
                raise ValueError(
                    f"{field_name!r} must be a dict/list (JSON or Python literal), "
                    f"got {raw!r}"
                )
        return str(obj)

    return str(raw).strip()


# --- Lookups --------------------------------------------------------------

def resolve_fiscal_year(session, label):
    """Return the FiscalYear id for a label like 'FY24', or None."""
    if _is_empty(label):
        return None
    fy = (
        session.query(FiscalYear)
        .filter(FiscalYear.fy == str(label).strip(), FiscalYear.deleted == False)
        .first()
    )
    return fy.id if fy else None


def resolve_trustfund(session, identifier):
    """Resolve a trust fund by name, then pcode, then grant number.

    Returns (trustfund_id, team_id) or (None, None). Case-insensitive on name.
    """
    if _is_empty(identifier):
        return None, None
    ident = str(identifier).strip()

    base = session.query(TrustFund).filter(TrustFund.deleted == False)
    tf = base.filter(TrustFund.name.ilike(ident)).first()
    if tf is None:
        tf = base.filter(TrustFund.pcode == ident).first()
    if tf is None:
        tf = base.filter(TrustFund.grant == ident).first()
    if tf is None:
        return None, None
    return tf.id, tf.team_id


# --- Report types ---------------------------------------------------------

@dataclass
class RowResult:
    index: int                 # 0-based row position in the source file
    trust_fund: str
    fiscal_year: str
    ok: bool = True
    errors: list = dc_field(default_factory=list)
    created: list = dc_field(default_factory=list)   # field names inserted
    updated: list = dc_field(default_factory=list)   # field names changed
    unchanged: list = dc_field(default_factory=list)  # field names already equal


@dataclass
class ImportReport:
    dry_run: bool
    rows: list = dc_field(default_factory=list)

    @property
    def ok_rows(self):
        return [r for r in self.rows if r.ok]

    @property
    def error_rows(self):
        return [r for r in self.rows if not r.ok]

    def summary(self):
        created = sum(len(r.created) for r in self.rows)
        updated = sum(len(r.updated) for r in self.rows)
        unchanged = sum(len(r.unchanged) for r in self.rows)
        mode = "DRY RUN (nothing written)" if self.dry_run else "COMMITTED"
        lines = [
            f"=== Batch import: {mode} ===",
            f"Rows: {len(self.rows)}  ok: {len(self.ok_rows)}  errors: {len(self.error_rows)}",
            f"Fields  created: {created}  updated: {updated}  unchanged: {unchanged}",
        ]
        for r in self.error_rows:
            lines.append(
                f"  ! row {r.index + 1} [{r.trust_fund} / {r.fiscal_year}]: "
                + "; ".join(r.errors)
            )
        return "\n".join(lines)


# --- Engine ---------------------------------------------------------------

def _upsert(session, tf_id, fy_id, team_id, field_name, value, dry_run, now):
    """Insert/update one grant_info_long row. Returns 'created'|'updated'|'unchanged'."""
    existing = (
        session.query(GrantInfo)
        .filter(
            GrantInfo.trustfund_id == tf_id,
            GrantInfo.fiscal_year_id == fy_id,
            GrantInfo.field == field_name,
            GrantInfo.deleted == False,
        )
        .first()
    )
    if existing is not None:
        if existing.value == value:
            return "unchanged"
        if not dry_run:
            existing.value = value
            existing.updated_at = now
        return "updated"

    if not dry_run:
        session.add(GrantInfo(
            trustfund_id=tf_id, fiscal_year_id=fy_id, field=field_name,
            value=value, team_id=team_id, deleted=False,
            created_at=now, updated_at=now,
        ))
    return "created"


def import_rows(session, rows, dry_run=True):
    """Import an iterable of dict rows into grant_info_long.

    Each row maps column name -> cell value. ``trust_fund`` and ``fiscal_year``
    identify the submission; every other recognized column is a field. Unknown
    columns and empty cells are skipped. One DB transaction per row: a row with
    any error is rolled back as a unit, so the import is all-or-nothing per row.
    """
    report = ImportReport(dry_run=dry_run)
    now = datetime.datetime.now()

    for i, row in enumerate(rows):
        tf_label = row.get(TRUSTFUND_COLUMN)
        fy_label = row.get(FISCAL_YEAR_COLUMN)
        result = RowResult(
            index=i,
            trust_fund="" if _is_empty(tf_label) else str(tf_label).strip(),
            fiscal_year="" if _is_empty(fy_label) else str(fy_label).strip(),
        )

        tf_id, team_id = resolve_trustfund(session, tf_label)
        fy_id = resolve_fiscal_year(session, fy_label)
        if tf_id is None:
            result.ok = False
            result.errors.append(f"unknown trust fund {tf_label!r}")
        if fy_id is None:
            result.ok = False
            result.errors.append(f"unknown fiscal year {fy_label!r}")

        # Validate + stage every field before touching the DB.
        staged = []  # (field_name, encoded_value)
        for col, raw in row.items():
            if col in ID_COLUMNS or _is_empty(raw):
                continue
            if col not in FIELD_KINDS:
                result.errors.append(f"unknown column {col!r} (ignored)")
                continue
            try:
                staged.append((col, encode_value(col, raw)))
            except ValueError as exc:
                result.ok = False
                result.errors.append(str(exc))

        if not result.ok:
            session.rollback()
            report.rows.append(result)
            continue

        try:
            for field_name, value in staged:
                outcome = _upsert(session, tf_id, fy_id, team_id,
                                  field_name, value, dry_run, now)
                getattr(result, outcome).append(field_name)
            if dry_run:
                session.rollback()
            else:
                session.commit()
        except Exception as exc:  # noqa: BLE001 - report, don't crash the batch
            session.rollback()
            result.ok = False
            result.errors.append(f"db error: {exc}")

        report.rows.append(result)

    return report
