"""Step 40 — quality control.

Runs db/qc/checks.sql, then reads meta.qc_result back and decides whether the
build passes. Errors fail the run with a non-zero exit code so CI stops;
warnings are printed and tolerated.

This is the step that earns trust in the maps. Nothing gets published from a
failed QC run.

Usage:
    python pipelines/40_qc.py
    python pipelines/40_qc.py --strict     # warnings also fail
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from common import ROOT, log, step
from common import db


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    args = parser.parse_args()

    step("40", "Quality control")

    os.environ.setdefault("PGOPTIONS", f"-c ghana.git_sha={git_sha()}")
    db.run_sql_file(ROOT / "db" / "qc" / "checks.sql")

    run_id = db.scalar("SELECT max(id) FROM meta.qc_run")
    rows = db.fetch(
        """
        SELECT severity, check_name, target, observed, expected, detail
        FROM meta.qc_result
        WHERE run_id = %s AND NOT passed
        ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                 check_name
        """,
        (run_id,),
    )

    total = db.scalar("SELECT count(*) FROM meta.qc_result WHERE run_id = %s", (run_id,))
    errors = [r for r in rows if r[0] == "error"]
    warnings = [r for r in rows if r[0] == "warning"]

    log.info("%d checks run: %d errors, %d warnings",
             total, len(errors), len(warnings))

    for severity, name, target, observed, expected, detail in rows:
        log.log(
            40 if severity == "error" else 30,
            "%-9s %-32s %-28s observed=%s expected=%s%s",
            severity.upper(), name, target, observed, expected,
            f"\n           {detail}" if detail else "",
        )

    if errors or (args.strict and warnings):
        log.error("QC failed. Nothing should be published from this build.")
        sys.exit(1)

    log.info("QC passed. Safe to export and publish.")


if __name__ == "__main__":
    main()
