"""Command-line batch importer for the F4D portal.

Usage (from F4D-main/, with the venv active):

  # 1. Generate a blank template + data dictionary to fill in:
  ./venv/Scripts/python.exe batch_import.py --template results_template.csv

  # 2. Dry-run a filled sheet (validates, writes NOTHING, prints a report):
  ./venv/Scripts/python.exe batch_import.py results_2024.csv

  # 3. Commit for real once the dry-run is clean:
  ./venv/Scripts/python.exe batch_import.py results_2024.csv --commit

Accepts .csv or .xlsx (.xlsx needs openpyxl installed). The same engine
(f4d.batch.core) backs the in-app upload page, so behavior is identical.
"""

import argparse
import sys

import pandas as pd

from connection import create_session
from f4d.batch import core


def load_rows(path):
    """Read a CSV/Excel file into a list of {column: value} dicts.

    Empty cells come through as None (not NaN) so the engine skips them.
    """
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)
    df = df.where(pd.notnull(df), None)
    df.columns = [str(c).strip() for c in df.columns]
    return df.to_dict(orient="records")


def write_template(path):
    """Emit a blank template with all columns + a sibling data dictionary."""
    columns = [core.TRUSTFUND_COLUMN, core.FISCAL_YEAR_COLUMN] + list(core.FIELD_KINDS)
    pd.DataFrame(columns=columns).to_csv(path, index=False)

    dict_path = path.rsplit(".", 1)[0] + "_DATA_DICTIONARY.md"
    kind_help = {
        core.TEXT: "free text",
        core.LIST: "comma-separated list (e.g. `Kenya, Uganda`)",
        core.INT: "a whole-number id",
        core.BLOB: "a JSON object/array (advanced; leave blank if unsure)",
    }
    lines = [
        "# F4D batch-import template — data dictionary",
        "",
        "One row per (trust fund x fiscal year). Leave a cell blank to skip that",
        "field — blanks never overwrite existing data, so partial sheets are safe.",
        "",
        "| Column | Required | Format |",
        "|---|---|---|",
        f"| `{core.TRUSTFUND_COLUMN}` | yes | trust fund name, P-code, or grant number |",
        f"| `{core.FISCAL_YEAR_COLUMN}` | yes | fiscal year label exactly as in the portal (e.g. `FY24`) |",
    ]
    for name, kind in core.FIELD_KINDS.items():
        lines.append(f"| `{name}` | no | {kind_help[kind]} |")
    with open(dict_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return dict_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Batch-import F4D results data.")
    parser.add_argument("file", nargs="?", help="CSV/XLSX file to import")
    parser.add_argument("--commit", action="store_true",
                        help="write to the database (default is a dry run)")
    parser.add_argument("--template", metavar="PATH",
                        help="write a blank template + data dictionary and exit")
    args = parser.parse_args(argv)

    if args.template:
        dict_path = write_template(args.template)
        print(f"Wrote template: {args.template}")
        print(f"Wrote data dictionary: {dict_path}")
        return 0

    if not args.file:
        parser.error("provide a file to import, or --template to generate one")

    rows = load_rows(args.file)
    session = create_session()
    try:
        report = core.import_rows(session, rows, dry_run=not args.commit)
    finally:
        session.close()

    print(report.summary())
    if not args.commit:
        print("\nDry run only. Re-run with --commit to write these changes.")
    # Non-zero exit if any row failed, so this is CI/script friendly.
    return 1 if report.error_rows else 0


if __name__ == "__main__":
    sys.exit(main())
