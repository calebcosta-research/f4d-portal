"""Scan for report data that leaked from one grant onto another.

Read-only. Nothing is written, updated or deleted.

WHY THIS EXISTS
---------------
Until the session-state fix, Streamlit kept a TTL's form state alive for the
whole browser tab. A TTL who reports for several grants and logged out of one
and into the next in the same tab carried the previous grant's answers into the
next grant's form. Lending Operations was the worst case: ``operation_list`` and
``cpf_list`` were only read from the database "if the session is empty", so the
first report opened in a tab stayed in the list, and Save wrote that list to
whichever trust fund was current -- copying one grant's operations onto another.

This script finds the fingerprint that leak leaves behind: the *same* value
stored against *different* trust funds. It reports candidates for a human to
check with the TTL. It does not decide what is wrong and it does not fix
anything.

CONFIDENCE
----------
Every cluster is ranked, because identical text across two grants is not proof:

  HIGH    the trust funds share a TTL (per trustfunds.ttl) -- exactly the
          person who could have hit the bug -- and the text is substantial.
  MEDIUM  same TTL but short text, or different TTLs with long, distinctive
          text (>= --long-chars, default 200).
  LOW     different TTLs and shorter text. Usually boilerplate; skim and move on.

Sorted highest-confidence first, so the top of the output is where to look.

USAGE (on the VDI)
------------------
    $env:sql_username="EFI_Admin"; $env:sql_password="<password>"
    py scan_cross_grant_dupes_pytds.py                  # default sections
    py scan_cross_grant_dupes_pytds.py --fy FY26        # one fiscal year only
    py scan_cross_grant_dupes_pytds.py --all-sections   # + deliverables/indicators
    py scan_cross_grant_dupes_pytds.py --min-chars 0    # lower the length floor
    py scan_cross_grant_dupes_pytds.py --csv dupes.csv  # also write a CSV

Uses python-tds (``import pytds``), the same pure-Python driver as the other
maintenance scripts, so it imports under the VDI's group-policy DLL block.

Env overrides: sql_host, sql_database, sql_port, db_schema.
"""
import argparse
import ast
import csv
import getpass
import os
import sys
from collections import defaultdict

SCHEMA = os.environ.get("db_schema", "f4d")

# Sections written by the code paths that could leak. Each entry is
# (label, SQL predicate on `field`, is_blob).
#
# `operations` and `cpfs` are the proven write-path leak: session_state lists
# saved against whatever trust fund was current. The narrative fields are plain
# free text -- long prose repeated verbatim under two grants is a strong signal.
CORE_SECTIONS = [
    ("operations", "field LIKE 'operation[_]%'", True),
    ("cpfs", "field LIKE 'cpf[_]%'", True),
    ("collaborations", "field LIKE 'collaboration[_]%'", True),
    ("narrative", (
        "field IN ('challenges','strategic_objective','overall_progress',"
        "'implementation_challenges','public_communication_external',"
        "'public_communication_internal')"), False),
]

# Off by default: these are keyed per trust fund so a leak is unlikely, and
# mapped indicators differ between grants, so matches are mostly noise.
EXTRA_SECTIONS = [
    ("deliverables", "field = 'deliverables'", True),
    ("custom_indicators", "field = 'custom_indicators'", True),
]


def connect():
    import pytds
    user = os.environ.get("sql_username") or input("SQL username: ").strip()
    password = os.environ.get("sql_password") or getpass.getpass("SQL password: ")
    return pytds.connect(
        os.environ.get("sql_host", "WBGMSSQLEFIP001"),
        os.environ.get("sql_database", "WBG"), user, password,
        port=int(os.environ.get("sql_port", "5800")),
        autocommit=False, login_timeout=15)


def fingerprint(value, is_blob):
    """Normalize a stored value so formatting differences don't hide a match.

    Blob sections store ``str(dict)``. Two saves of the same dict produce the
    same string, but re-serializing with sorted keys also catches values that
    were rewritten in a different key order. Returns None for values that carry
    no information (empty, or every field blank), which would otherwise match
    across dozens of unrelated grants.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    if is_blob:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return " ".join(text.split())
        return _canonical(_strip_empty(parsed))

    return " ".join(text.split())


def _strip_empty(obj):
    """Drop empty/placeholder members so near-blank records don't match."""
    if isinstance(obj, dict):
        cleaned = {}
        for key, val in obj.items():
            val = _strip_empty(val)
            if val not in (None, "", {}, [], "None"):
                cleaned[key] = val
        return cleaned
    if isinstance(obj, list):
        items = [_strip_empty(v) for v in obj]
        return [v for v in items if v not in (None, "", {}, [], "None")]
    if isinstance(obj, str):
        return " ".join(obj.split())
    return obj


def _canonical(obj):
    if isinstance(obj, dict):
        if not obj:
            return None
        return "{" + ",".join(f"{k!r}:{_canonical(obj[k])}"
                              for k in sorted(obj, key=str)) + "}"
    if isinstance(obj, list):
        if not obj:
            return None
        return "[" + ",".join(str(_canonical(v)) for v in obj) + "]"
    return repr(obj)


def load_rows(cur, predicate, fy=None):
    params = []
    where = ["g.deleted = 0", predicate]
    if fy:
        where.append("f.fy = %s")
        params.append(fy)
    sql = (
        "SELECT g.id, g.trustfund_id, t.name, t.grant, t.ttl, f.fy, "
        "       g.field, g.value, g.created_at, g.updated_at "
        f"FROM {SCHEMA}.grant_info_long g "
        f"LEFT JOIN {SCHEMA}.trustfunds t ON t.id = g.trustfund_id "
        f"LEFT JOIN {SCHEMA}.fys f ON f.id = g.fiscal_year_id "
        f"WHERE {' AND '.join(where)}"
    )
    cur.execute(sql, tuple(params))
    cols = ("id", "trustfund_id", "tf_name", "grant", "ttl", "fy",
            "field", "value", "created_at", "updated_at")
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def cluster(rows, is_blob, min_chars):
    """Group rows by fingerprint, keeping only groups spanning >1 trust fund."""
    buckets = defaultdict(list)
    for row in rows:
        fp = fingerprint(row["value"], is_blob)
        if fp is None or len(fp) < min_chars:
            continue
        buckets[fp].append(row)

    clusters = []
    for fp, members in buckets.items():
        if len({m["trustfund_id"] for m in members}) < 2:
            continue  # same grant across fiscal years is normal carry-forward
        clusters.append((fp, sorted(members, key=lambda m: (m["created_at"] or "",
                                                            m["id"]))))
    return clusters


def rank(fp, members, long_chars):
    """Score a cluster. Shared TTL is the signal that matters most."""
    ttls = {(m["ttl"] or "").strip().lower() for m in members if (m["ttl"] or "").strip()}
    shared_ttl = len(ttls) == 1
    substantial = len(fp) >= long_chars
    if shared_ttl and substantial:
        return "HIGH", "same TTL, substantial text"
    if shared_ttl:
        return "MEDIUM", "same TTL, short value"
    if substantial:
        return "MEDIUM", "different TTLs, long distinctive text"
    return "LOW", "different TTLs, short value"


_RANK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def preview(fp, width=160):
    return fp if len(fp) <= width else fp[:width] + " ..."


def report(findings, csv_path=None):
    if not findings:
        print("\nNo duplicate values found across different trust funds.")
        print("Nothing to review -- the leak does not appear to have reached the data.")
        return

    findings.sort(key=lambda f: (_RANK_ORDER[f["rank"]], -len(f["fingerprint"])))
    by_rank = defaultdict(int)
    for f in findings:
        by_rank[f["rank"]] += 1

    print("\n" + "=" * 78)
    print(f"{len(findings)} duplicate cluster(s): "
          f"{by_rank['HIGH']} HIGH, {by_rank['MEDIUM']} MEDIUM, {by_rank['LOW']} LOW")
    print("=" * 78)

    for i, f in enumerate(findings, 1):
        print(f"\n[{i}] {f['rank']}  ({f['reason']})  section={f['section']}")
        print(f"    value: {preview(f['fingerprint'])}")
        print("    stored against:")
        for m in f["members"]:
            print(f"      - {m['tf_name']} / {m['grant'] or '?'}  {m['fy'] or '?'}  "
                  f"field={m['field']}  ttl={m['ttl'] or '?'}")
            print(f"        row id={m['id']}  created={m['created_at']}  "
                  f"updated={m['updated_at']}")
        print("    (earliest row listed first -- the later one is the likely copy)")

    print("\n" + "-" * 78)
    print("Next step: confirm with the TTL which grant the text really belongs to")
    print("before changing anything. This script does not modify the database.")

    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["cluster", "rank", "reason", "section", "row_id",
                             "trustfund_id", "trustfund", "grant", "ttl", "fy",
                             "field", "created_at", "updated_at", "value"])
            for i, f in enumerate(findings, 1):
                for m in f["members"]:
                    writer.writerow([i, f["rank"], f["reason"], f["section"],
                                     m["id"], m["trustfund_id"], m["tf_name"],
                                     m["grant"], m["ttl"], m["fy"], m["field"],
                                     m["created_at"], m["updated_at"], m["value"]])
        print(f"CSV written: {csv_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fy", help="limit to one fiscal year, e.g. FY26")
    ap.add_argument("--all-sections", action="store_true",
                    help="also scan deliverables and custom_indicators blobs")
    ap.add_argument("--min-chars", type=int, default=12,
                    help="ignore values shorter than this once normalized (default 12)")
    ap.add_argument("--long-chars", type=int, default=200,
                    help="length at which a value counts as distinctive (default 200)")
    ap.add_argument("--csv", help="also write the findings to this CSV file")
    args = ap.parse_args()

    sections = list(CORE_SECTIONS)
    if args.all_sections:
        sections += EXTRA_SECTIONS

    try:
        conn = connect()
    except Exception as exc:  # noqa: BLE001 - surface whatever the driver said
        print(f"Could not connect: {exc}")
        return 1

    findings = []
    try:
        with conn.cursor() as cur:
            print(f"schema={SCHEMA}  fy={args.fy or 'all'}  "
                  f"sections={', '.join(s[0] for s in sections)}")
            for label, predicate, is_blob in sections:
                rows = load_rows(cur, predicate, args.fy)
                clusters = cluster(rows, is_blob, args.min_chars)
                print(f"  {label:<18} {len(rows):>5} rows -> "
                      f"{len(clusters)} cross-grant duplicate cluster(s)")
                for fp, members in clusters:
                    level, reason = rank(fp, members, args.long_chars)
                    findings.append({"section": label, "fingerprint": fp,
                                     "members": members, "rank": level,
                                     "reason": reason})
    finally:
        conn.close()

    report(findings, args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
