from __future__ import annotations

import json
import unittest
from pathlib import Path

from repair_lab import TargetAccountTool, build_campaign_plan


class IdentityTest(unittest.TestCase):
    """Test campaign planning identity: logical company count and row preservation."""

    def setUp(self):
        """Load fixture accounts."""
        self.accounts = json.loads(
            Path("fixtures/target_accounts.json").read_text()
        )

    def count_logical_companies(self, accounts: list[dict]) -> int:
        """Count logical companies by company_id.

        Identity rule: two rows are the same logical company iff they share
        a non-null, non-empty company_id. A row with no company_id is its own company.
        """
        seen: set[str | None] = set()
        for row in accounts:
            company_id = row.get("company_id")
            # Treat None and empty string as distinct per-row identities
            if company_id:
                seen.add(company_id)
            else:
                # Row with no company_id: use its row id as unique identity
                seen.add(row.get("id"))
        return len(seen)

    def test_page_size_10_resolves_to_209_companies(self):
        """Page size 10 should capture all 209 logical companies."""
        plan = build_campaign_plan(
            TargetAccountTool(self.accounts),
            brand_kit_id="brand-kit-meridian-2026",
            template_id="template-abm-q3",
            page_size=10,
        )

        # Assert exactly 209 rows in source_row_ids (one per logical company)
        self.assertEqual(len(plan["source_row_ids"]), 209,
                        f"Page size 10: expected exactly 209 source_row_ids, got {len(plan['source_row_ids'])}")

        # Count distinct logical companies in the plan
        observed_companies: set[str] = set()
        company_id_counts: dict[str, int] = {}
        for row_id in plan["source_row_ids"]:
            for account in self.accounts:
                if account["id"] == row_id:
                    company_id = account.get("company_id")
                    if company_id:
                        observed_companies.add(company_id)
                        company_id_counts[company_id] = company_id_counts.get(company_id, 0) + 1
                    else:
                        observed_companies.add(row_id)
                    break

        self.assertEqual(len(observed_companies), 209,
                        f"Page size 10: expected 209 companies, got {len(observed_companies)}")

        # Assert no company_id appears more than once
        duplicates = {cid: count for cid, count in company_id_counts.items() if count > 1}
        self.assertFalse(duplicates,
                        f"Page size 10: found duplicate company_ids: {duplicates}")

    def test_page_size_25_resolves_to_209_companies(self):
        """Page size 25 should capture all 209 logical companies."""
        plan = build_campaign_plan(
            TargetAccountTool(self.accounts),
            brand_kit_id="brand-kit-meridian-2026",
            template_id="template-abm-q3",
            page_size=25,
        )

        # Assert exactly 209 rows in source_row_ids (one per logical company)
        self.assertEqual(len(plan["source_row_ids"]), 209,
                        f"Page size 25: expected exactly 209 source_row_ids, got {len(plan['source_row_ids'])}")

        observed_companies: set[str] = set()
        company_id_counts: dict[str, int] = {}
        for row_id in plan["source_row_ids"]:
            for account in self.accounts:
                if account["id"] == row_id:
                    company_id = account.get("company_id")
                    if company_id:
                        observed_companies.add(company_id)
                        company_id_counts[company_id] = company_id_counts.get(company_id, 0) + 1
                    else:
                        observed_companies.add(row_id)
                    break

        self.assertEqual(len(observed_companies), 209,
                        f"Page size 25: expected 209 companies, got {len(observed_companies)}")

        # Assert no company_id appears more than once
        duplicates = {cid: count for cid, count in company_id_counts.items() if count > 1}
        self.assertFalse(duplicates,
                        f"Page size 25: found duplicate company_ids: {duplicates}")

    def test_page_size_100_resolves_to_209_companies(self):
        """Page size 100 should capture all 209 logical companies."""
        plan = build_campaign_plan(
            TargetAccountTool(self.accounts),
            brand_kit_id="brand-kit-meridian-2026",
            template_id="template-abm-q3",
            page_size=100,
        )

        # Assert exactly 209 rows in source_row_ids (one per logical company)
        self.assertEqual(len(plan["source_row_ids"]), 209,
                        f"Page size 100: expected exactly 209 source_row_ids, got {len(plan['source_row_ids'])}")

        observed_companies: set[str] = set()
        company_id_counts: dict[str, int] = {}
        for row_id in plan["source_row_ids"]:
            for account in self.accounts:
                if account["id"] == row_id:
                    company_id = account.get("company_id")
                    if company_id:
                        observed_companies.add(company_id)
                        company_id_counts[company_id] = company_id_counts.get(company_id, 0) + 1
                    else:
                        observed_companies.add(row_id)
                    break

        self.assertEqual(len(observed_companies), 209,
                        f"Page size 100: expected 209 companies, got {len(observed_companies)}")

        # Assert no company_id appears more than once
        duplicates = {cid: count for cid, count in company_id_counts.items() if count > 1}
        self.assertFalse(duplicates,
                        f"Page size 100: found duplicate company_ids: {duplicates}")

    def test_page_size_10_preserves_rows_2401_through_2406(self):
        """Rows 2401-2406 should survive at page size 10."""
        plan = build_campaign_plan(
            TargetAccountTool(self.accounts),
            brand_kit_id="brand-kit-meridian-2026",
            template_id="template-abm-q3",
            page_size=10,
        )

        source_row_ids = set(plan["source_row_ids"])
        for row_num in range(2401, 2407):
            row_id = f"row-{row_num}"
            self.assertIn(row_id, source_row_ids,
                         f"Page size 10: {row_id} missing from source_row_ids")

    def test_page_size_25_preserves_rows_2401_through_2406(self):
        """Rows 2401-2406 should survive at page size 25."""
        plan = build_campaign_plan(
            TargetAccountTool(self.accounts),
            brand_kit_id="brand-kit-meridian-2026",
            template_id="template-abm-q3",
            page_size=25,
        )

        source_row_ids = set(plan["source_row_ids"])
        for row_num in range(2401, 2407):
            row_id = f"row-{row_num}"
            self.assertIn(row_id, source_row_ids,
                         f"Page size 25: {row_id} missing from source_row_ids")

    def test_page_size_100_preserves_rows_2401_through_2406(self):
        """Rows 2401-2406 should survive at page size 100."""
        plan = build_campaign_plan(
            TargetAccountTool(self.accounts),
            brand_kit_id="brand-kit-meridian-2026",
            template_id="template-abm-q3",
            page_size=100,
        )

        source_row_ids = set(plan["source_row_ids"])
        for row_num in range(2401, 2407):
            row_id = f"row-{row_num}"
            self.assertIn(row_id, source_row_ids,
                         f"Page size 100: {row_id} missing from source_row_ids")


if __name__ == "__main__":
    unittest.main()
