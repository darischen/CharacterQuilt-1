from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


REQUIRED_ASSET_TYPES = (
    "landing_page",
    "linkedin_ad_1",
    "linkedin_ad_2",
    "linkedin_ad_3",
)


@dataclass(frozen=True)
class ToolPage:
    rows: list[dict[str, Any]]
    next_cursor: str | None
    truncated: bool


class AccountPageLoader(Protocol):
    def load_page(
        self,
        *,
        cursor: str | None = None,
        page_size: int = 25,
    ) -> ToolPage: ...


class TargetAccountTool:
    """Deterministic stand-in for the paginated uploaded-account service."""

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(account) for account in accounts]

    def load_page(
        self,
        *,
        cursor: str | None = None,
        page_size: int = 25,
    ) -> ToolPage:
        start = int(cursor or "0")
        rows = self._accounts[start : start + page_size]
        next_index = start + len(rows)
        next_cursor = (
            str(next_index) if next_index < len(self._accounts) else None
        )
        return ToolPage(
            rows=rows,
            next_cursor=next_cursor,
            truncated=next_cursor is not None,
        )


def _collapse_page(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse rows that name the same company.

    The uploaded list can name a company more than once, so the page is
    reduced to one row per company before anything downstream sees it.
    """
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        company_id = str(row["company_id"])
        if company_id in seen:
            continue
        seen.add(company_id)
        kept.append(row)
    return kept


def _build_incomplete_plan(
    rows_collected: list[dict[str, Any]],
    uploaded_accounts: list[dict[str, Any]] | None,
    reason: str,
    brand_kit_id: str,
    template_id: str,
) -> dict[str, Any]:
    """Build a plan with incomplete=False and a termination reason."""
    # Dedupe the rows collected so far
    seen_keys: dict[str, str] = {}
    deduplicated_rows: list[dict[str, Any]] = []
    identity_collisions: dict[str, list[str]] = {}

    for row in rows_collected:
        row_id = str(row["id"])
        company_id = row.get("company_id")
        if company_id:
            dedup_key = str(company_id)
        else:
            dedup_key = row_id

        if dedup_key in seen_keys:
            winning_row_id = seen_keys[dedup_key]
            if winning_row_id not in identity_collisions:
                identity_collisions[winning_row_id] = []
            identity_collisions[winning_row_id].append(row_id)
        else:
            seen_keys[dedup_key] = row_id
            deduplicated_rows.append(row)

    plan_result: dict[str, Any] = {
        "source_row_ids": [str(row["id"]) for row in deduplicated_rows],
        "deliverables": _make_deliverables(
            deduplicated_rows,
            brand_kit_id=brand_kit_id,
            template_id=template_id,
        ),
        "identity_collisions": identity_collisions,
        "complete": False,
        "failure_reason": reason,
    }

    # Calculate expected vs actual if we have uploaded accounts
    if uploaded_accounts is not None:
        expected_keys: set[str] = set()
        for account in uploaded_accounts:
            company_id = account.get("company_id")
            if company_id:
                expected_keys.add(str(company_id))
            else:
                expected_keys.add(str(account["id"]))

        actual_keys = set(seen_keys.keys())
        plan_result["expected_companies"] = len(expected_keys)
        plan_result["actual_companies"] = len(actual_keys)

    return plan_result


def _make_deliverables(
    accounts: list[dict[str, Any]],
    *,
    brand_kit_id: str,
    template_id: str,
) -> list[dict[str, str]]:
    deliverables: list[dict[str, str]] = []
    for account in accounts:
        effective_brand_kit = str(
            account.get("saved_brand_kit_id", brand_kit_id)
        )
        effective_template = str(
            account.get("saved_template_id", template_id)
        )
        for asset_type in REQUIRED_ASSET_TYPES:
            deliverables.append(
                {
                    "source_row_id": str(account["id"]),
                    "company_id": str(account["company_id"]),
                    "company_name": str(account["company_name"]),
                    "asset_type": asset_type,
                    "brand_kit_id": effective_brand_kit,
                    "template_id": effective_template,
                }
            )
    return deliverables


def build_campaign_plan(
    tool: AccountPageLoader,
    *,
    brand_kit_id: str,
    template_id: str,
    page_size: int = 25,
    uploaded_accounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    all_rows: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str | None] = set()
    row_ids_seen: set[str] = set()

    while True:
        page = tool.load_page(cursor=cursor, page_size=page_size)

        # Check for truncated without cursor: claims more data but provides no way to get it
        if page.truncated and page.next_cursor is None:
            return _build_incomplete_plan(
                all_rows,
                uploaded_accounts,
                reason="truncated_without_cursor",
                brand_kit_id=brand_kit_id,
                template_id=template_id,
            )

        # Check for stalled cursor: no rows but claims more remain
        if len(page.rows) == 0 and page.truncated:
            return _build_incomplete_plan(
                all_rows,
                uploaded_accounts,
                reason="stalled_cursor",
                brand_kit_id=brand_kit_id,
                template_id=template_id,
            )

        # Accumulate rows and track which ones are new
        new_row_count = 0
        for row in page.rows:
            row_id = str(row["id"])
            if row_id not in row_ids_seen:
                new_row_count += 1
                row_ids_seen.add(row_id)
        all_rows.extend(page.rows)

        # Check for cycling cursor: if next_cursor was already returned before AND no new
        # rows, we are in a true cycle (not just a repeated token that advances)
        if page.truncated and page.next_cursor in seen_cursors and new_row_count == 0:
            return _build_incomplete_plan(
                all_rows,
                uploaded_accounts,
                reason="cycling_cursor",
                brand_kit_id=brand_kit_id,
                template_id=template_id,
            )

        if not page.truncated:
            break
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor

    # Dedupe across full result set keyed on company_id (or row id if company_id is null/empty)
    seen_keys: dict[str, str] = {}  # key -> winning row id
    deduplicated_rows: list[dict[str, Any]] = []
    identity_collisions: dict[str, list[str]] = {}  # winning row id -> list of absorbed row ids

    for row in all_rows:
        row_id = str(row["id"])
        company_id = row.get("company_id")

        # Determine the dedup key: company_id if present and non-empty, otherwise row id
        if company_id:
            dedup_key = str(company_id)
        else:
            dedup_key = row_id

        if dedup_key in seen_keys:
            # Collision: this row is a duplicate of an earlier one
            winning_row_id = seen_keys[dedup_key]
            if winning_row_id not in identity_collisions:
                identity_collisions[winning_row_id] = []
            identity_collisions[winning_row_id].append(row_id)
        else:
            # First occurrence of this key
            seen_keys[dedup_key] = row_id
            deduplicated_rows.append(row)

    # Determine completeness by comparing against uploaded accounts
    plan_result: dict[str, Any] = {
        "source_row_ids": [str(row["id"]) for row in deduplicated_rows],
        "deliverables": _make_deliverables(
            deduplicated_rows,
            brand_kit_id=brand_kit_id,
            template_id=template_id,
        ),
        "identity_collisions": identity_collisions,
    }

    if uploaded_accounts is not None:
        # Resolve uploaded accounts under identity rule
        expected_keys: set[str] = set()
        for account in uploaded_accounts:
            company_id = account.get("company_id")
            if company_id:
                expected_keys.add(str(company_id))
            else:
                expected_keys.add(str(account["id"]))

        # Count what we actually got
        actual_keys = set(seen_keys.keys())

        if actual_keys == expected_keys:
            plan_result["complete"] = True
        else:
            # Short read: terminated cleanly but covered fewer companies than uploaded
            plan_result["complete"] = False
            plan_result["failure_reason"] = "short_read"
            plan_result["expected_companies"] = len(expected_keys)
            plan_result["actual_companies"] = len(actual_keys)
    else:
        # Without uploaded_accounts reference, assume complete
        plan_result["complete"] = True

    return plan_result


def evaluate_campaign_coverage(
    plan: dict[str, Any],
    accounts: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Evaluate campaign coverage by iterating uploaded accounts, not surviving rows.

    This catches missing companies that the plan failed to deliver.
    """
    deliverables = plan.get("deliverables", [])

    # Resolve uploaded accounts under identity rule to get expected companies
    expected_companies: dict[str, str] = {}  # dedup_key -> representative row_id
    for account in accounts:
        row_id = str(account["id"])
        company_id = account.get("company_id")
        # Dedup key: company_id if present, else row id
        if company_id:
            dedup_key = str(company_id)
        else:
            dedup_key = row_id

        # Keep first occurrence for each key
        if dedup_key not in expected_companies:
            expected_companies[dedup_key] = row_id

    # Check each expected company has complete asset set in deliverables
    missing_companies = []
    for dedup_key, expected_row_id in expected_companies.items():
        # Find deliverables for any row that maps to this company identity
        # We need to find which rows in the plan represent this company
        observed_row_ids: set[str] = set()
        for deliverable in deliverables:
            deliverable_row_id = str(deliverable.get("source_row_id", ""))
            # Check if this row belongs to the expected company
            for account in accounts:
                if str(account["id"]) == deliverable_row_id:
                    account_company_id = account.get("company_id")
                    if account_company_id:
                        row_dedup_key = str(account_company_id)
                    else:
                        row_dedup_key = str(account["id"])

                    if row_dedup_key == dedup_key:
                        observed_row_ids.add(deliverable_row_id)
                    break

        if not observed_row_ids:
            missing_companies.append(dedup_key)
            continue

        # Check asset types for this company
        observed_types: set[str] = set()
        for deliverable in deliverables:
            if str(deliverable.get("source_row_id")) in observed_row_ids:
                observed_types.add(str(deliverable.get("asset_type")))

        if observed_types != set(REQUIRED_ASSET_TYPES):
            return False, f"company {dedup_key} has incomplete asset set: {observed_types}"

    if missing_companies:
        return False, f"missing companies: {missing_companies}"

    if plan.get("complete") is not True:
        return False, "campaign did not declare completion"

    return True, f"all {len(expected_companies)} expected companies have complete asset sets"
