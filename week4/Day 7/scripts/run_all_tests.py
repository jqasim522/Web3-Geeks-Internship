#!/usr/bin/env python3
"""
scripts/run_all_tests.py — Day 6 test runner.

# STATUS: OFFLINE-CODE (this script itself has never been run — no lib/ was
#          present in the environment that wrote it)
# RUN: python scripts/run_all_tests.py
# EXPECTED: Runs every test category except `live/` (real credentials
#           required for those — run them separately, deliberately, with
#           `pytest tests/live/ -m live -v -s`). Writes a coverage report
#           to `coverage_report/` and a plain-text summary to stdout.

This script does not invent pass/fail numbers — it shells out to pytest and
prints/relays whatever pytest itself reports. If it is run before `lib/` is
in place, pytest will fail at collection time (ImportError) for every file
that imports from `lib/`, which is expected and not a bug in this script.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    args = [
        sys.executable,
        "-m",
        "pytest",
        str(ROOT / "tests"),
        "-m",
        "not live",
        "-v",
        "--tb=short",
        f"--cov={ROOT / 'lib'}",
        "--cov-report=term-missing",
        f"--cov-report=html:{ROOT / 'coverage_report'}",
    ]

    print("Day 6 test run — excluding tests/live/ (run those separately)")
    print(f"Command: {' '.join(args)}")
    print("-" * 70)

    result = subprocess.run(args, cwd=ROOT)

    print("-" * 70)
    if result.returncode == 0:
        print("All non-live tests passed. See coverage_report/index.html for coverage.")
    else:
        print(
            f"pytest exited with code {result.returncode}. "
            "See output above for failures — this script does not summarize "
            "or reinterpret pytest's own result, per the 'never fabricate "
            "results' rule for this suite."
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
