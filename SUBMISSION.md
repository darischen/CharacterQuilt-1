# Submission

- Time Spent: 2 hours 30 minutes
Working time: ~2h30 on the exercise. Commit timestamps run past that because I finished the completeness and termination work before the 2:30 mark and then wrote it up without committing along the way. The final commit lands after the window as a result. The transcript shows the actual sequence.

- Transcript (file or link): transcript.md
- `make demo` output: **The 204 line is demo.py's own count, which folds the six null company_ids into one key. 209 is the resolved company count.**
list                          : fixtures/target_accounts.json
uploaded rows                 : 223
brand kit selected on request : brand-kit-meridian-2026
template selected on request  : template-abm-q3

                                  page_size=10    page_size=25   page_size=100
rows campaigned                            209             209             209
deliverables                               836             836             836
distinct company_id in plan                204             204             204
complete flag                             True            True            True

deliverables by brand kit (page_size=25):
  brand-kit-2019-legacy                36
  brand-kit-meridian-2026             800

shipped check returned        : True
shipped check said            : all 209 expected companies have complete asset sets


- `make test` output:

test_page_size_100_preserves_rows_2401_through_2406 (test_identity.IdentityTest.test_page_size_100_preserves_rows_2401_through_2406)
Rows 2401-2406 should survive at page size 100. ... ok
test_page_size_100_resolves_to_209_companies (test_identity.IdentityTest.test_page_size_100_resolves_to_209_companies)
Page size 100 should capture all 209 logical companies. ... ok
test_page_size_10_preserves_rows_2401_through_2406 (test_identity.IdentityTest.test_page_size_10_preserves_rows_2401_through_2406)
Rows 2401-2406 should survive at page size 10. ... ok
test_page_size_10_resolves_to_209_companies (test_identity.IdentityTest.test_page_size_10_resolves_to_209_companies)
Page size 10 should capture all 209 logical companies. ... ok
test_page_size_25_preserves_rows_2401_through_2406 (test_identity.IdentityTest.test_page_size_25_preserves_rows_2401_through_2406)
Rows 2401-2406 should survive at page size 25. ... ok
test_page_size_25_resolves_to_209_companies (test_identity.IdentityTest.test_page_size_25_resolves_to_209_companies)
Page size 25 should capture all 209 logical companies. ... ok
test_supplied_evaluator_accepts_the_published_plan (test_visible.SuppliedEvaluatorSmokeTest.test_supplied_evaluator_accepts_the_published_plan) ... ok

----------------------------------------------------------------------
Ran 7 tests in 1.375s

OK

- `make verify` output:
list                          : fixtures/second_list.json
uploaded rows                 : 115
brand kit selected on request : brand-kit-meridian-2026
template selected on request  : template-abm-q3

                                  page_size=10    page_size=25   page_size=100
rows campaigned                             99              99              99
deliverables                               396             396             396
distinct company_id in plan                 98              98              98
complete flag                             True            True            True

deliverables by brand kit (page_size=25):
  brand-kit-meridian-2026             396

shipped check returned        : True
shipped check said            : all 99 expected companies have complete asset sets

209 on the first list, 99 on the second. The shapes differ. The first list is a pagination and identity problem together: duplicates spread across pages, six null company_ids, and three EMEA pairs sharing a domain with their parent. The second is identity only: a higher repeat rate (15 of 97 ids against 13 of 203), no shared domains across ids, no brand kit overrides, and two null rows the fixture names "Unresolved Import A" and "B". A count that held on both is evidence the rule is not fitted to the first file.

- The one thing you found yourself rather than took from the agent:
  - I found the page-size instability in make demo because in the same list, it showed 214 rows at page sizes 10 and 25, but at page size 100 it says 211. The whole time with the page size list differences it said complete: True which was incorrect.
- The claim in this submission you are least sure of, and how you checked it:
  - The identity call on `company-kestrel-robotics` and `company-copperline-energy` was the one I'm least sure about because one id spans two domains. I kept them merged on the view that an explicit id outranks typos so I flagged them both for review. I found this by enumerating the neighboring counts and confirmed each failed for the stated reason, and that domain based alternative breaks the three EMEA pairs.
- Anything a reviewer should know before opening the repository:
  - Model switched mid way since the context window was nearing compaction, and I didn't want to truncate or corrupt the transcript, so I switched to Sonnet 5 with 1m token context window.
  - evidence/ holds the instrumentation harness I ran against the five loaders in sources.py. I created it as a diagnostic and not a test.
  - src/sources.py is unchanged. I interpreted this file as the environment simulating the problems instead of code to repair.