#!/usr/bin/env python3
"""Test build_campaign_plan against faulty loaders from sources.py with timeouts."""
from __future__ import annotations

import json
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

# Add src to path - working from scratchpad, go up 3 levels to project root
project_src = Path("C:\\Users\\daris\\Downloads\\01-campaign-audit-v2\\01-campaign-audit\\src")
sys.path.insert(0, str(project_src))

from repair_lab import build_campaign_plan, evaluate_campaign_coverage
from sources import (
    ReplayingLoader,
    StallingLoader,
    CyclingLoader,
    SilentlyShortLoader,
    TruncatedWithoutCursorLoader,
    ALL_SOURCES,
)


def run_with_timeout(timeout_seconds: int, func, *args, **kwargs) -> tuple[bool, Any, str]:
    """Run func with timeout. Returns (completed, result, message)."""
    result = {"value": None, "exception": None, "completed": False}

    def target():
        try:
            result["value"] = func(*args, **kwargs)
            result["completed"] = True
        except Exception as e:
            result["exception"] = e
            result["completed"] = True

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        return False, None, "HUNG (timeout)"
    elif result["exception"] is not None:
        exc = result["exception"]
        tb = traceback.format_exc()
        return True, exc, f"RAISED: {type(exc).__name__}: {exc}\n{tb}"
    else:
        return True, result["value"], "TERMINATED"


def count_load_page_calls(loader: Any) -> int:
    """Extract call count from loader if it has _calls."""
    return getattr(loader, "_calls", 0)


def test_loader(loader_class, accounts: list[dict], request: dict) -> dict:
    """Test one loader. Return results dict."""
    loader_name = loader_class.__name__

    # Wrap loader to track calls if it doesn't have _calls
    class WrappedLoader:
        def __init__(self, inner_loader):
            self._inner = inner_loader
            self._tracked_calls = 0

        def load_page(self, **kwargs):
            self._tracked_calls += 1
            return self._inner.load_page(**kwargs)

    inner = loader_class(accounts)
    loader = WrappedLoader(inner)
    initial_count = len(accounts)

    print(f"\n{'='*70}")
    print(f"Testing: {loader_name}")
    print(f"{'='*70}")
    print(f"Seeded with: {initial_count} rows")

    # Run build_campaign_plan with timeout
    completed, plan, message = run_with_timeout(
        30,
        build_campaign_plan,
        loader,
        brand_kit_id="brand-kit-test",
        template_id="template-test",
    )

    print(f"Execution: {message}")

    # Get call count from wrapper or inner loader
    call_count = loader._tracked_calls
    if call_count == 0:
        call_count = count_load_page_calls(inner)

    result = {
        "loader": loader_name,
        "seeded_rows": initial_count,
        "execution": message,
        "completed": completed,
        "exception": None,
        "load_page_calls": call_count,
        "rows_returned": None,
        "plan_complete": None,
        "coverage_passed": None,
        "coverage_detail": None,
    }

    # Extract exception if raised
    if isinstance(plan, Exception):
        result["exception"] = f"{type(plan).__name__}: {str(plan)}"
        print(f"Exception: {result['exception']}")

    # If completed successfully, analyze plan
    if completed and plan is not None and not isinstance(plan, Exception):
        rows_returned = len(plan.get("source_row_ids", []))
        result["rows_returned"] = rows_returned
        result["plan_complete"] = plan.get("complete")

        print(f"load_page calls: {result['load_page_calls']}")
        print(f"Rows returned: {rows_returned}")
        print(f"plan['complete']: {result['plan_complete']}")

        # Run evaluate_campaign_coverage
        try:
            passed, detail = evaluate_campaign_coverage(plan, accounts)
            result["coverage_passed"] = passed
            result["coverage_detail"] = detail
            print(f"evaluate_campaign_coverage: {passed} ({detail})")
        except Exception as e:
            result["coverage_passed"] = False
            result["coverage_detail"] = f"Exception: {type(e).__name__}: {e}"
            print(f"evaluate_campaign_coverage raised: {result['coverage_detail']}")

    return result


def main():
    # Load test data
    project_root = Path("C:\\Users\\daris\\Downloads\\01-campaign-audit-v2\\01-campaign-audit")
    accounts = json.loads((project_root / "fixtures" / "target_accounts.json").read_text())
    request = json.loads((project_root / "fixtures" / "request.json").read_text())

    print(f"Loaded {len(accounts)} accounts from target_accounts.json")
    print(f"Request: brand_kit={request['brand_kit']['id']}, template={request['template']['id']}")

    all_results = []

    # Test each loader
    for loader_class in ALL_SOURCES:
        result = test_loader(loader_class, accounts, request)
        all_results.append(result)

    # Summary table
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Loader':<30} {'Status':<15} {'Rows':<8} {'Coverage':<10}")
    print(f"{'-'*30} {'-'*15} {'-'*8} {'-'*10}")

    for result in all_results:
        status = "[OK]" if result["completed"] and result["exception"] is None else "[FAIL]"
        rows = str(result["rows_returned"]) if result["rows_returned"] is not None else "N/A"
        coverage = "PASS" if result["coverage_passed"] else "FAIL" if result["coverage_passed"] is False else "N/A"
        print(f"{result['loader']:<30} {status:<15} {rows:<8} {coverage:<10}")

    # Detailed summary
    print(f"\n{'='*70}")
    print("SURVIVES vs FAILS")
    print(f"{'='*70}")

    survives = [r for r in all_results if r["completed"] and r["exception"] is None]
    fails = [r for r in all_results if not r["completed"] or r["exception"] is not None]

    print(f"\nCurrent code SURVIVES ({len(survives)}):")
    for result in survives:
        print(f"  - {result['loader']}")
        if result["coverage_passed"]:
            print(f"    [PASS] Coverage passes")
        else:
            print(f"    [FAIL] Coverage fails: {result['coverage_detail']}")

    print(f"\nCurrent code FAILS ({len(fails)}):")
    for result in fails:
        if result["exception"]:
            print(f"  - {result['loader']}: {result['exception']}")
        else:
            print(f"  - {result['loader']}: {result['execution']}")


if __name__ == "__main__":
    main()