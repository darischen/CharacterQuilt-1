# Decisions

Short notes are fine. Fill this in before you submit.

- Time actually spent: 2hrs 30 min. Commit timestamps run past that because I finished the completeness and termination work before the 2:30 mark and then wrote it up without committing along the way. The final commit lands after the window as a result. The transcript shows the actual sequence.
- How many logical companies this upload represents, and why that number and
  not a neighbouring one:
  209. Two rows are the same company if and only if they share a non-null, non-empty company_id; a row without one is its own company, since nothing in it establishes a match. 203 distinct non-null ids plus six id-less rows on six domains.

  223 is the raw row count and treats "Sable Works", "SABLE WORKS", and "SABLE WORKS Inc" as three companies. 217 counts rows with a usable id, same problem. 214 and 211 are what the starter reports at different page sizes, so they measure paging. 204 treats null as a key and merges six unrelated businesses. 206 collapses on domain and breaks the EMEA subsidiaries, which carry distinct ids on a domain shared with their parent. 211 also splits the two ids whose rows disagree on domain; I kept those merged and flagged them, since an explicit id outranks what looks like a typo.

- What changed between your roadmap and what you shipped:
  The roadmap listed six planned fixes. I shipped three of them: identity, completeness, and termination. The brand kit precedence rule did not get done. I also expected to detect stalling as its own reason code, and the frozen cursor in StallingLoader trips cycling_cursor instead, which is correct behaviour but not what I had written down.

- What you had the coding agent do, and where you overrode it:
  The agent did a read-only map of the repo, wrote the loader harness, and wrote the fixes once I specified the invariants. I overrode it three times. Its first loader report classified "did not raise" as surviving, which put the two silent-corruption cases in the same column as the clean ones; I reclassified. Its harness reported 0 load_page calls for SilentlyShortLoader, which was a getattr default on a class with no _calls attribute; the real count is 5. And its first termination fix broke ReplayingLoader from 209 down to 47 by treating any repeated cursor as cycling, when that loader repeats a page and then advances.

  I also wrote the identity test to assert coverage only, and caught that it passed at 209 while make demo reported 214. Coverage and exactness are different assertions, and the first one let five duplicates through.

- What your change guarantees, and what it only makes more likely:
  Guaranteed: the count no longer moves with page size, an id-less row is never merged into another, every merge is recorded, and a plan reporting complete has been compared against the upload it came from.
  
  Not guaranteed: that 209 is the number the customer means. It is the number their data supports under a stated rule. If two of their rows are the same business under different ids, my rule counts two and says so rather than guessing.

- What you fixed at the cause, and what you only stopped from showing:
  All three shipped changes are cause fixes. Nothing was suppressed. The brand kit override is a fourth cause I found and left, not a symptom I hid.

- For at least one defect: the command that demonstrated it, pasted with its
  output, before your fix and after:
The defect: the number of companies in the plan changes with the page size, and the shipped check passes every time.

$ make demo    # before

list                          : fixtures/target_accounts.json
uploaded rows                 : 223
brand kit selected on request : brand-kit-meridian-2026
template selected on request  : template-abm-q3

                                  page_size=10    page_size=25   page_size=100
rows campaigned                            214             214             211
deliverables                               856             856             844
distinct company_id in plan                204             204             204
complete flag                             True            True            True

deliverables by brand kit (page_size=25):
  brand-kit-2019-legacy                36
  brand-kit-meridian-2026             820

shipped check returned        : True
shipped check said            : all 214 campaigned rows have the requested asset types

Three answers for one list, complete: True on all three, check green on all three. 214 carries five duplicate companies; 211 has lost three of the six null-id rows to page collisions while still carrying duplicates, so the two errors partly cancel.

$ make demo    # after

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

The 204 line is demo.py's own tally, which folds the six null company_ids into one key. 209 is the resolved count.
- What you chose not to fix:
Nine rows carry saved_brand_kit_id: brand-kit-2019-legacy, silently overriding the kit named on the request, which accounts for 36 of 836 deliverables and matches the customer's complaint about creative in the wrong brand. The fix is a precedence rule, request wins and the override is recorded. I ran out of budget after the three causes above. second_list.json carries no overrides, so make verify would not catch a regression here.

- What you are still unsure about, including anything that came up during the
  session and stayed open:
  Whether company-kestrel-robotics and company-copperline-energy should stay merged. One id, two domains, and row-1217 sits on another company's domain. I kept the id and flagged both for review.
  
  Whether 209 satisfies the customer. It is the number the failed run reported, and they rejected it. My position is that the count was fine and the check behind it was empty, but I cannot rule out that they were also disputing the figure itself.

  stalled_cursor never fires against the current mocks. It covers an empty page claiming truncation, and no loader in sources.py produces that shape.
  
  The rerun that never came back. failure-traces.jsonl shows a repeated next_cursor followed by worker_timeout, which resembles ReplayingLoader, but I did not trace it far enough to say the production hang and the mock share a cause.

- Where the thing I found myself shows up:

I ran `make demo` in a separate terminal, outside the agent session, before directing any of the work. That is where the page-size instability came from:

$ make demo

                                  page_size=10    page_size=25   page_size=100
rows campaigned                            214             214             211
deliverables                               856             856             844
distinct company_id in plan                204             204             204
complete flag                             True            True            True

shipped check returned        : True
shipped check said            : all 214 campaigned rows have the requested asset types

One list, three answers, `complete: True` and a green check on all three. That became the opening line of the roadmap and the reason identity went first rather than pagination.

Because I ran it outside the agent session, the command itself is not in transcript.md. What is in the transcript is what it caused: I told the agent to write the identity test as an assertion across page sizes 10, 25, and 100 before any fix, which only makes sense if you already know the number moves. The same numbers appear again in the before-output above and in the
`make demo` block in this file.