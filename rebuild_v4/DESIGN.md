# SER v4 pipeline design

Each failure seen so far is fixed at the earliest stage that can fix it. Sources: CIKM 2026 and SIGIR 2026 reviews (`desires2027/REVIEWS_ORIGINAL.md`), the demo regression (`desires2027/scripts/demo_regression_results.json`), the Mexican error analysis (`desires2027/scripts/mexican_errors.py`), the eval memory (fused table, two pillars), and direct reading of v3 data on 2026-10-24.

## Failure cases and where each is fixed

| # | Failure | Evidence | Fixed at |
|---|---|---|---|
| F1 | Pronouns and the reviewer as audience | CIKM R2; `self` on 97% of recipes; "I plan to take my own advice" -> self | Extract (Rule 6) |
| F2 | Cuisine from an ingredient, venue, or side dish | Mexican precision 25% -> 55% (CIKM R3, R4); "mexican cheese", "Mexican restaurant", "served it with Mexican rice" | Extract (Rule 8) |
| F3 | Attribute of another dish or recipe | "Delicious Chicken Pot Pie" -> taste delicious; "served with steamed broccoli" -> side-dish on Bourbon Chicken | Extract (Rule 7) |
| F4 | Changes and plans read as attributes | "the sauce needed thickening" -> texture thickening; "next time more garlic" | Extract (Rule 7) |
| F5 | Occasion not when the dish was eaten | "made this a month before Thanksgiving" -> Thanksgiving | Extract (Rule 7) |
| F6 | Non-texture in texture | v3 texture has easy, perfectly, nicely, right shape; [easy weeknight chicken] routes easy to texture, 1 result | Extract (Rule 9) |
| F7 | Generic praise as flavor | delicious, good, great are 40+ blacklist entries in v3 | Extract (Rule 9), blacklist kept as backstop |
| F8 | Inflected variants as separate facets | crispy / crisp / crispness (CIKM R4); thick / thicker, fluffy / fluffier, flaky / flakey | Extract (Rule 4, base form) then loop |
| F9 | Context dims marked negative and then dropped | Christmas marked negative because the sprouts were not crispy | Extract (Rule 10) |
| F10 | Synonym clusters (tart/zesty -> tangy, hubby/DH -> husband) | paper Algorithm 1, recall pillar | Normalization loop, by Claude |
| F11 | Facets that cover most items filter nothing | husband 96%, self 97%, kids 62%; paper Lesson 1 | Aggregate (support count) |
| F12 | Span not locatable | ~14% dropped by FindSpan in v2 | Extract (exact copy) + Ground |
| F13 | Cook vs eater confusion | SIGIR R1 W2 | Extract (v1 rule kept, example added) |

Out of scope for this rebuild: movies and games data ([funny movie for date night] -> House of Wax), query routing (`ser-search.js`), new dimensions (the six v1 dimensions are kept, no Difficulty).

## Stages

1. **Extract.** `scripts/extract.py`, prompt `extraction_prompt_v2.md`, deepseek-v4-flash on NRP, thinking off, T=0.2. Output `data/raw_extractions_v4.jsonl`, one row per review, same schema as v1 plus `model`, `prompt`, `error`.
2. **Ground.** Keep an item only if `source_text` is found in the review and the entity (or its base form) is in or follows from that span. Drop negative sentiment as v1 did. Report the drop rate.
3. **Normalize.** Observe-act-apply loop per category, by Claude reading the frequency-sorted values. Each round writes `normalization/round_N.md` (what was merged, blacklisted, and why) and updates `data/synonyms_v4.json`, `data/blacklist_v4.json`. Stop when the top 30 values cover at least 80% of mentions, or a round gains no more than 2 points (feature-normalization skill).
4. **Aggregate.** Per recipe and value, support = number of distinct reviews asserting it. Membership threshold chosen from the support distribution, recorded with its effect on coverage. Support kept in the data for ranking.
5. **Build exhibit.** Start from the v3 exhibit JSON (catalog fields, Main ingredient, cook time, calories unchanged). Replace the review-derived fields and `reviews[].attributes`. Write `data/food-exhibit-data-500recipes.v4.json`; swap into the demo only after tagging.
6. **Verify.** `desires2027/scripts/demo_regression.py`, `desires2027/scripts/test_paper_queries.py`, `scripts/check.py`. Rebuild the mention-level precision judge (gpt-oss, full sentence, rubric rejecting negation, off-topic, ingredient-only, cook-only), because the original eval scripts are lost.
