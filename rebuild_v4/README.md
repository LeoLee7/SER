# SER v4 rebuild log

Goal: rebuild the recipe review facets with a stronger extractor, then normalize with the paper's observe-act-apply loop (Algorithm 1), with Claude reading the frequency distributions and deciding each mapping by hand. Nothing outside this directory is overwritten until the final swap, and every swap is preceded by a git tag.

## How to return to a state

| State | How to restore |
|---|---|
| Live demo before v4 (gemma3 extraction, v3 normalization) | `git checkout v3-deployed-2026-10-24` (tag, pushed to GitHub); data file also at `food-exhibit-data-500recipes.json.bak.v4pre-rebuild` |
| v4 data | `rebuild_v4/data/food-exhibit-data-500recipes.v4.json`, rebuildable with `scripts/build_exhibit.py` from `data/verified_v4.jsonl` + maps |
| Paper numbers (Table 1, Table 2) | Computed on the v2/v3 data in that tag with the CIKM scripts, recovered to `cikm_eval/` from git history (commit 321f6bf of the CIKM repo). |

## Pipeline

| Step | File | Status |
|---|---|---|
| Prompt v1 (copy of the one used for v2/v3 data) | `prompts/extraction_prompt_v1.md` | reference |
| Prompt v2 = v1 + Rules 6 to 9 | `prompts/extraction_prompt_v2.md` | drafted 2026-10-24 |
| Extraction (deepseek-v4-flash, NRP, thinking off, T=0.2) | `scripts/extract.py` -> `data/raw_extractions_v4.jsonl` | done 2026-10-25, 10,000 reviews, 2650s |
| Ground + verify | `scripts/ground.py`, `scripts/verify.py` -> `data/grounded_v4.jsonl`, `data/verified_v4.jsonl` | done 2026-10-25 (10,000 reviews, 0 errors, 15,370 items kept) |
| Normalization loop rounds | `normalization/ROUNDS.md`, `observe_round{0,1,2}.md`, `data/synonyms_v4.json`, `data/blacklist_v4.json` | done, 2 rounds |
| Exhibit rebuild (catalog fields kept from v3, review fields recomputed) | `scripts/build_exhibit.py` -> `data/food-exhibit-data-500recipes.v4.json` | done; swapped into the local demo, v3 backed up as `food-exhibit-data-500recipes.json.bak.v4pre-rebuild`; NOT pushed |
| Regression | `desires2027/scripts/demo_regression.py`, `test_paper_queries.py` -> `data/demo_regression_v4.json` | PASS (crisp folded, no pronouns, no self, paper queries PASS) |
| Held-out blind eval (100 fresh reviews, old v3 vs v4) | `scripts/make_blind.py` -> `heldout/`, `scripts/score_blind.py heldout` -> `data/heldout_scores.txt` | done: precision 52% -> 82%, recall proxy 72% -> 78% |

## Decisions

- 2026-10-24. Model choice. NRP models benchmarked on 8 real reviews with the production prompt, thinking disabled (`chat_template_kwargs.enable_thinking=false`). deepseek-v4-flash: median 8.2s, 8/8 valid JSON. gemma (current): 10.6s, 8/8. gpt-oss: 15.7s, 8/8, sparse. qwen3: 19.0s, 8/8. glm-5, kimi, minimax-m2 ignore the thinking switch and exhaust 1500 tokens (0 to 5/8 valid). Chosen: deepseek-v4-flash.
- 2026-10-24. Prompt v2 rules, each tied to an observed v1 error:
  - Rule 6 (not the reviewer): "I plan to take my own advice" became audience `self`; `self` covers 97% of recipes.
  - Rule 7 (only this dish): "served with steamed broccoli" became meal_type `side-dish` on Bourbon Chicken; "Delicious Chicken Pot Pie" (another recipe's name) became taste `delicious`.
  - Rule 8 (cuisine only when named): stronger models on v1 invent "homestyle American (pie crust)".
  - Rule 9 (short entities, texture is physical feel): v3 texture values include `easy`, `perfectly`, `nicely`, `right shape`.
- 2026-10-24. Synonym folding is NOT done in the prompt beyond v1's Rule 4 (kept unchanged); folding belongs to the loop so its effect stays measurable.
- 2026-10-24. Eval scripts recovered: deleted from the CIKM repo working tree but present in its git history (commit 321f6bf, 2026-06-06). Exported unchanged to `cikm_eval/` (30 scripts, 7 analysis docs, all tables). Lessons from `cikm_eval/METRICS_NOTES.md` folded into `DESIGN.md`: precision is set by the extractor (flat across loop stages, ~55% with gemma3), cuisine modifier-vs-dish was left as prompt-level future work, 20% of merges distort meaning (meal -> casual), judge cells of n=30 are too small.
- 2026-10-25. Prompt iterations, all files kept: `v2_draft1` (first rules) -> `v2_draft2` (rewritten rule set, second example) -> `v2_draft3` (memory/gift, ingredient-not-flavor) -> `v2` (cuisine allows "Chinese chicken dish", generic praise list explicit). Test sets: `data/testset16_ids.json` (stress patterns), `data/val100_ids.json` (random, seed 42).
- 2026-10-25. gpt-oss judge (CIKM rubric) on val100, both sides after the v3 blacklist: old 68% (163/238), new 78% (168/216). Treated as indicative only: that rubric accepts ingredient cuisine ("Italian seasoning" judged correct). Per Li, this stage is judged by Claude subagents instead, blind (`blind/`, rubric `blind/RUBRIC.md`, key hidden, `scripts/score_blind.py`). 10 of 100 reviews skipped because their text did not match the v3 exhibit.
- 2026-10-25. Blind round 1 (4 Claude subagents, 308 tuples, 90 reviews): old v3 demo precision 50% (109/220), new v2b 59% (125/211). Main residual errors: preference statements and reasons for changes ("because I like a more bold taste"). Claude spot-checked the verdicts: mostly right, a few strict (e.g. "warming lunch or dinner" marked plan).
- 2026-10-25. Prompt v2 (draft4 -> v2): preference/reason and hypothetical rules, positive examples for meal/occasion recall. Claude judged the 22 new unseen tuples directly (`blind2/annot_0.json`).
- 2026-10-25. Added `scripts/ground.py` (deterministic backstops: generic praise incl. CIKM v2 judge-derived terms, vague audience, comparisons, >3 words) and `scripts/verify.py` + `prompts/verify_prompt_v1.md` (second deepseek pass with the rubric). Scores on val100 from `scripts/score_file.py`: grounded 65% prec / 79% recall proxy; grounded+verified 80% / 76%. Caveat: val100 was used for tuning and the verifier shares the rubric's definition, so final numbers must come from a fresh held-out sample.
- 2026-10-25. Prompts and scripts frozen (`FROZEN_2026-10-25.sha1`). Full run started: `scripts/run_full.sh` -> `data/raw_extractions_v4.jsonl`, `grounded_v4.jsonl`, `verified_v4.jsonl`, log `data/run_full.log`.
- 2026-10-25. Held-out blind eval: 100 reviews never used in tuning (seed 11, val100/test16/sample10 excluded), 285 tuples, 4 Claude subagents, rubric `heldout/RUBRIC.md` plus a fairness note on prospective serving contexts. Old v3 vs v4: precision 52% (119/230) -> 82% (129/157); recall proxy 72% -> 78%. Per category precision: taste 32 -> 54, texture 65 -> 92, meal 60 -> 93, occasion 75 -> 81, audience 48 -> 90, cuisine 43 -> 100 (n=3). Weak spots: meal type recall 72 -> 56, cuisine recall 100 -> 50 (n small), taste precision still 54% (ingredients as flavor, preference statements). Recall proxy = correct values from either version + annotator-listed misses, so it is relative, not absolute.
