"""Step 30 — run the analysis SQL.

Each file in db/analysis/ is self-contained, ends with its own validation
block, and drops and rebuilds its own tables. Running them in order is
therefore always safe and always reproducible from core.

Usage:
    python pipelines/30_run_analysis.py
    python pipelines/30_run_analysis.py --only 02_flood_exposure
"""

from __future__ import annotations

import argparse

from common import ROOT, log, step
from common import db

ANALYSIS_DIR = ROOT / "db" / "analysis"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="run one file, by stem")
    args = parser.parse_args()

    step("30", "Spatial analysis")

    files = sorted(ANALYSIS_DIR.glob("*.sql"))
    if args.only:
        files = [f for f in files if f.stem == args.only or f.stem.endswith(args.only)]
        if not files:
            raise SystemExit(f"no analysis file matching '{args.only}'")

    for path in files:
        log.info("--- %s ---", path.name)
        try:
            db.run_sql_file(path)
        except RuntimeError as exc:
            # H3 rollups depend on an optional extension. A missing optional
            # dependency should not stop flood exposure from running.
            if "h3" in path.name:
                log.warning("%s skipped: %s", path.name, exc)
                continue
            raise

    log.info("Step 30 complete. Next: 40_qc.py")


if __name__ == "__main__":
    main()
