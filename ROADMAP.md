# Roadmap


## What went wrong and how I know
The starter's own output disagrees with itself. make demo runs the same list at three page sizes and reports 214 rows campaigned at 10 and 25, then 211 at 100, with complete: True and a passing check every time. make verify does the same on the second list: 103, 100, 98. A count that moves with the page size is not a count of anything, and nothing in the pipeline notices.

Three causes sit underneath that. Evidence for the pagination behaviours comes from evidence/test_loaders.py, which runs build_campaign_plan against each loader in sources.py under a 30s timeout and counts calls.

**Cause 1: cursor advancement never verified**
build_campaign_plan trusts page.truncated and page.next_cursor without checking if the cursor is actually moving or not. For example:
 - StallingLoader keeps the cursor at the same value of 50 without travelling further, and the program keeps trying until the budget limit of 400 is reached.
 - CyclingLoader wraps the cursor to 0 instead of terminating, which causes the program to keep trying until the budget limit of 400 is reached.
 - TruncatedWithoutCursorLoader returns truncated=True with next_cursor=None. cursor=None is not a valid value for next_cursor because cursor will just start over at 0, and the program keeps trying until the budget limit of 400 is reached.

**Cause 2: completeness never compared to input**
evaluate_campaign_coverage checks that every row already in the plan has all 4 asset types and that the plan["complete"] is True, but doesn't check that the output contains all rows that were seeded. build_campaign_plan also sets complete to True unconditionally at the end of the loop. This is the customer's "I do not believe the number it gave us": a plan that loses 107 rows still reports itself finished, and the shipped check agrees because it only ever looks at rows that survived.

**Cause 3: identity never defined**

Nothing says what makes a row a company. _collapse_page() dedupes by company_id within a page, so repeats in later pages survive, and str(None) becomes the key "None", so id-less rows collide whenever two share a page. make demo shows both: 214 rows campaigned at page_size 10 and 25, 211 at page_size 100, complete: True throughout. The answer moves with the paging.

The duplicates the customer saw come from the rule, not from a paging failure. Under company_id identity, company-northwind-energy and company-northwind-energy-emea are separate companies sharing northwind-energy.example, as are the Sable Fitness and Tessellate Capital pairs, and row-1217 sits on copperline-group.example. Spot-checking twenty rows, you see the same company twice and cannot tell whether it is one customer or two.

ReplayingLoader shows the check hiding duplication rather than causing it: 428 rows returned for 223 seeded, all 428 kept in source_row_ids, and evaluate_campaign_coverage calls set() on that list, reports 214, and passes while the deliverables carry the duplication through.

## How many logical companies this upload represents
**Identity rule**: two rows are the same logical company if and only if they share a non-null and non-empty company_id. A row with no company_id is its own logical company because there's no way to tell if it is the same as another row with no company_id. Merging the two rows with no company_id would silently combine unrelated rows.

**The number is 209.** 223 rows carry 203 distinct non-null company_id values. 6 rows have a null company_id and six distinct domains. 203 + 6 = 209.

The neighboring numbers all fail. 223 is the raw row count, and names like "SABLE WORKS" or "Sable Works" or "SABLE WORKS Inc" are counted as 3 companies not 1. 217 counts rows carrying a usable id and has the same problem. 214 is what the shipped code reports at page_size 25, but the same code reports 211 at page_size 100, so it measures pagination rather than companies. 204 treats null as a key and folds six unrelated businesses into one. 206 collapses on domain, which breaks the EMEA subsidiaries: they carry distinct ids on a domain shared with their parent. 211 splits the two ids whose rows disagree on domain, company-kestrel-robotics and company-copperline-energy. I keep those merged, on the view that an explicit id outranks what looks like a data-entry error, and flag both pairs for review rather than deciding silently.

Trace `t-9f21` reports 209 with complete: true and a passing check, but that is the number the customer rejected rather than evidence for it, and it is not what this repository produces. I think that 209 was defensible but unverifiable at the same time, and the check iterated only the rows that survived pagination, and never compared them to the upload. It also read a complete=True hardcoded value, sop it would've passed the same as a wrong number.

## What "complete" should mean
A plan is complete only if every row the source holds was read once and mapped to one logical company. complete=True only if:
 - Every logical company in the uploaded input appears in the plan exactly once. The upload is the reference, not the source's own report of itself. evaluate_campaign_coverage already receives accounts and never reads it; a source stopping early looks identical to a source finishing, so the comparison is the only thing that separates them.
 - No cursor value repeats within a run, and every page either returns rows or ends the read. This catches stalling and cycling without assuming cursors are ordered or numeric.
 - The count is invariant under page size. The same list read at 10, 25, and 100 returns the same number of logical companies.
 - Every identity collision resolved along the way is recorded in the plan, so a merge is auditable rather than silent.

Failing any of these sets complete=False with a machine-readable reason (stalled_cursor, cycling_cursor, truncated_without_cursor, budget_exhausted, short_read) and the count actually reached. A list that cannot be read completely should say so and say why, not report a smaller number as if it were the answer.

## What I changed and which changes removed a cause versus hid a symptom
**Identity, resolved across the whole run (removed a cause).** _collapse_page deduped within a page, so repeats in later pages survived and str(None) collided id-less rows whenever two shared a page. Resolution now runs over the full result set, keyed on company_id where present and the row's own id where it is null, and every merge is recorded under identity_collisions. make demo` went from 214 / 214 / 211 across page sizes to 209 / 209 / 209.

**Completeness derived, not asserted (removed a cause).** complete=True was hardcoded, and the check iterated only the rows that survived while ignoring the accounts argument it already received. Both now resolve the upload and compare against it. SilentlyShortLoader went from 116 rows passing to 116 rows, short_read, and 93 companies named as missing.

**Termination faults named (removed a cause).** The loop trusted truncated and never checked progress, so three loaders ran to the mock's call budget and raised. It now tolerates a repeated cursor that still yields new rows, and stops on one that does not. All five terminate. CyclingLoader collects all 209 rows and still reports complete=False, since a read that wrapped rather than ended cannot claim completeness.

Nothing I shipped hides a symptom; each change removes a reason the count was wrong or unverifiable.

**Found and left:** nine rows carry saved_brand_kit_id: brand-kit-2019-legacy, silently overriding the kit named on the request. 36 of 836 deliverables ship in the legacy kit. This is the customer's "creative is not in the brand we picked". The fix is a precedence rule, and I ran out of budget. `second_list.json` has no overrides, so `make verify` would not catch a regression here either way.

**Never fires:** stalled_cursor covers an empty page claiming truncation. No loader in sources.py produces that shape.

## Why the fix holds for the next list
The identity rule, cursor-progress check, and completeness definition are from whatever the loader returns at runtime. Nothing references a row count, a company_id, or a file name, which means that none of the code is specific to the first list. Applying it to second_list.json yields the same results, and the checks are still valid.

From running make verify, it showed that there are 99 logical companies instead of 209 for all three page sizes for the second list while 209 was consistent across all three page sizes for the first list.

The make verify command runs the same code against a different list, so a fix that only works on the first list would show up and would count as a failure.

## What I left uncertain or out of scope
 - Null handling for company_id. The customer couldn't tell some entries apart, and that could mean that the null rows are being pulled or that the shared company_id value is an issue, but that would be fixed by the identity rule.
 - StallingLoader/CyclingLoader/TruncatedWithoutCursorLoader retry behavior.
 - Rerun/timeout traces in the failture-traces.jsonl file.