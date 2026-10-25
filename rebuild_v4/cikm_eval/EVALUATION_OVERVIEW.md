# SER evaluation overview (organized, gold-free)

All numbers verified against `eval_data/`. We use an **LLM-as-a-judge** protocol
throughout: an independent model (gpt-oss on NRP-Nautilus, a different family from the
Gemma-3 extractor) grades extractions / relevance. Recipe counts are out of **500**.

The two benefits we demonstrate, and the three quantification methods that show them.

---

## Two pillars (the positioning)

SER's quality rests on two pillars, each with its own main mechanism:

| Pillar | Main mechanism | How it shows up |
| ------ | -------------- | --------------- |
| **Precision** | **Evidence-grounding** (primary) + context-aware extraction | every facet value is anchored to a verbatim review span (98-100% traceable; 100% at the DB level by construction); the LLM reads context and avoids the negation/off-topic false positives literal keyword matching returns (keyword genuine-rate as low as 41% for mother, 61% for spicy) |
| **Recall** | **Grouping** (synonym normalization) | scattered surface variants are consolidated into one clean facet (DH/hubby->husband, tart/zesty->tangy, greek->Mediterranean), widening coverage +19% over literal search |

**Multiple defense lines for quality** (not a single step):
1. Context-aware extraction (Gemma) -- avoids negation/irrelevant matches.
2. Evidence-grounding (span linking) -- drops un-locatable/hallucinated tags (the 14%
   FindSpan drop); 98-100% of kept tags trace to text.
3. Agentic filtering (blacklist) -- removes noise types.
4. Agentic merging (synonym map) -- the recall side.

**Scoping the earlier "precision has no advantage".** That statement was only about the
agentic normalization *round* (v1 -> v2): it relabels and filters at the attribute-type
level and does not re-verify individual extractions, so it adds no per-item precision
*delta*. It does NOT mean SER has no precision contribution -- precision is delivered by
the extraction and evidence-grounding stages, which are core parts of SER. We do not
understate that.

Some concepts show both pillars at once. **spicy** is the clearest: extraction first
discards the negation/ingredient noise (keyword genuine-rate only 61%), then normalization
merges heat/kick/hot into the facet.

---

## Method 1 - LLM-judged precision: keyword vs SER (shows benefit 1)

gpt-oss judges, per concept, whether each returned recipe genuinely fits. Keyword search
returns the word blindly; SER returns the extracted+normalized facet.

| Concept | Keyword precision | SER precision | Keyword's main false positives |
| ------- | ----------------: | ------------: | ------------------------------ |
| husband | 87% | 87% | (mostly genuine) |
| kids | 81% | 82% | "kids wouldn't touch it" (negation) |
| tangy | 88% | 85% | "not tangy" (few) |
| **spicy** | **61%** | 61% | "not spicy"; "spicy mustard" (ingredient) |
| mediterranean | 5/6 | 8/11 | "Mediterranean sea salt" (ingredient) |
| **mother** | **41%** | 44% | "used to make it" (memory); "gifted us" (not enjoying) |
| game-day | n/a (kw=0) | 79% | -- |

Reading: keyword precision is **concept-dependent**. For words that often appear in
negations or off-topic contexts (**spicy 61%, mother 41%**), keyword matching is poor and
contextual extraction is the win. For husband/tangy/kids the word is usually genuine
(81-88%), so there the benefit is recall (Method 2/3), not precision.

---

## Method 2 - Per-concept stage counts (shows where each stage helps)

Recipes found at each pipeline stage, with the synonyms folded in. (= Table 1 in
`COVERAGE_TREND_TABLE.md`, the curated concept set.)

| Concept | KW | +Gemma | v1 | v2 | Delta KW->v2 | folded at v1 / v2 |
| ------- | --: | --: | --: | --: | --: | --- |
| husband | 442 | 474 | 480 | 480 | +9% | hubby, dh / hubs |
| kids | 304 | 288 | 318 | 320 | +5% | children, kid, toddler / child |
| tangy | 41 | 32 | 61 | 73 | +78% | tang, tart / tartness, zesty, zingy |
| spicy | 158 | 128 | 172 | 174 | +10% | heat, kick, hot / fiery |
| game-day | 2 | 0 | 0 | 19 | (kw~0) | -- / super bowl, football game, game night |
| mediterranean | 6 | 1 | 1 | 11 | +83% | -- / greek |
| mother | 114 | 194 | 194 | 194 | +70% | (Gemma resolves mom/mum) |

Reading: a **negative** KW->+Gemma step (spicy 158->128) is benefit 1 (extraction drops
the negation/ingredient noise); a **positive** +Gemma->v1->v2 step is benefit 2 (merging).
mother gains at the Gemma step (it resolves mom/mum internally); game-day and
mediterranean exist only after v2 (long-tail / phrasal merges).

---

## Method 3 - Overall aggregate (the headline coverage number)

Summed over the top-20 real facets per category (a rough aggregate; double-counts
recipes, so we read it as a coverage index, not a per-recipe count).

| Category | Keyword | +Gemma | v1 | v2 | Uplift |
| -------- | ------: | -----: | --: | --: | -----: |
| Flavor | 1,527 | 1,378 | 1,777 | 1,870 | +22% |
| Texture | 1,727 | 1,801 | 1,801 | 1,801 | +4% |
| Meal | 999 | 1,092 | 1,241 | 1,269 | +27% |
| Occasion | 775 | 798 | 836 | 948 | +22% |
| Audience | 2,308 | 2,494 | 2,824 | 2,846 | +23% |
| Cuisine | 393 | 426 | 436 | 444 | +13% |
| **All** | **7,729** | **7,989** | **8,915** | **9,178** | **+19%** |

Reading: across all curated facets, SER surfaces +19% more recipes than literal keyword
search, concentrated in synonym-rich categories (Audience, Cuisine, Occasion).

---

## How the three methods relate

| Method | Granularity | Shows | Gold-free? |
| ------ | ----------- | ----- | ---------- |
| 1. LLM-judged precision (keyword vs SER) | per concept, judged | benefit 1 (extraction avoids negation/irrelevant) | judged sample |
| 2. Per-concept stage counts | per concept, deterministic | where each stage contributes; benefit 2 (merging) | yes |
| 3. Top-20 category aggregate | per category, deterministic | headline coverage gain (+19%) | yes |

Validation that the coverage gain is genuine recall: the pooled precision/recall study
(`tables/pr_trajectory.tex`) shows precision stays flat across stages while recall rises.

---

## The honest caveats (carried from the discussion)

- Keyword precision is concept-dependent; we do not claim SER precision is uniformly
  higher (husband/tangy keyword is already 87-88%).
- Method 3 sums memberships (double-counts); it is an index, not a recipe count.
- Residual noise remains in the deployed demo (self, etc.); the process is iterative.
- We report coverage gain (deterministic), not gold-based recall, since no exhaustive
  answer key exists (cf. on-demand KBP evaluation, Chaganty et al. 2017).
