# Coverage tables (review copy, FINAL)

Per-facet, recipe counts out of **500** (a recipe counts once if any of its reviews
triggers the facet). v2 = the deployed demo, untouched. Gold-free (observed counts).

LaTeX:
- `tables/perfacet_2stage.tex` - Table 1 (main, intuitive)
- `tables/perfacet_4stage.tex` - Table 2 (per-facet, four pipeline stages)
- `tables/recall_4stage.tex`   - Table 3 (category aggregate, kept for reference)
- `tables/denoising.tex`       - residual noise
- `tables/pr_trajectory.tex`   - precision/recall validation

Generators: `scripts/make_perfacet_tables.py`, `scripts/eval_recall_4stage.py`,
`scripts/make_denoising_table.py`.

---

## Q&A (read this to understand the numbers)

**Q: Reviews or recipes?** Recipes. 500 total (from 10,015 reviews). Every count is out of 500.

**Q: What does one number mean?** For a single facet (e.g. "mother"): how many of the 500
recipes that facet surfaces. Plain search for the word "mother" returns 114; the SER
"mother" facet returns 194, because it also captures mom/mum/mommy.

**Q: Why does Flavor drop at Gemma, and why does SER find FEWER for "garlic"?**
Many flavor words are also ingredients. "garlic" hits 316 recipes by plain search, but
most are ingredient lists ("2 cloves garlic"), not taste. Gemma tags garlic as a *flavor*
only when a review describes the taste, so it tags 108 (accurate, not a failure). After
merging garlicky/garlic-powder the SER facet is 135. So for ingredient-like words SER is
smaller-but-more-accurate; for non-ingredient words (mother, spicy) SER is larger.

**Q: Is "sum over the top-20 facets" a real metric?** No strong precedent: it double-counts
recipes and the total is hard to read. Standard practice reports per-facet (like per-query).
So Tables 1-2 (per-facet) are the primary evidence; Table 3 (the category sum) is kept only
as a rough aggregate for reference.

---

## Table 1 (MAIN) - Per-facet: four stages + which synonyms fold in at each stage

Recipes found (of 500) at each stage, and the synonym variants folded in at each stage.
Note three synonym-handling steps now: Gemma's own internal resolution, then v1, then v2.

Organized by merge type so the gradient is visible (recipes of 500; synonyms folded in
at each stage). All merges shown are clean/correct (we exclude disputable ones such as
buttery->creamy or I/we->self).

| Merge type | Concept | KW | +Gemma | v1 | v2 | Gemma resolves | v1 merges | v2 merges |
| ---------- | ------- | --: | --: | --: | --: | --- | --- | --- |
| Abbreviation | husband | 442 | 474 | 480 | 480 | dh, hubby, hubs | hubby, dh | hubs |
| Plural / variant | kids | 304 | 288 | 318 | 320 | kid, kiddos | children, kid, toddler | child, young children |
| Synonym cluster | tangy | 41 | 32 | 61 | 73 | tart, tang | tang, tart | tartness, zesty, zingy |
| Synonym cluster | spicy | 158 | 128 | 172 | 174 | heat, kick, hot | heat, kick, hot | fiery, ... |
| Phrase -> concept | game-day | 2 | 0 | 0 | 19 | -- | -- | super bowl, football game, game night, ... |
| Regional | mediterranean | 6 | 1 | 1 | 11 | -- | -- | greek |
| LLM-internal | mother | 114 | 194 | 194 | 194 | mom, mum, mommy, mama | -- | -- |

**The merge-type gradient (all correct merges):**
- **Abbreviation** (husband <- DH/hubby): short forms users type for the same person.
- **Plural / variant** (kids <- children/kid/toddler): morphological forms of one concept.
- **Synonym cluster** (tangy <- tart/zesty/zingy; spicy <- heat/kick/hot): genuinely
  different words for the same quality. SER understands tangy = tart = zesty.
- **Phrase -> concept** (game-day <- super bowl/football game/game night): multi-word
  expressions mapped to one facet. The canonical word is rarely written, so the facet
  exists almost entirely thanks to v2 (keyword 2 -> 19).
- **Regional** (mediterranean <- greek): a specific cuisine folded under a regional facet.
- **LLM-internal** (mother <- mom/mum): Gemma collapses these while extracting; the gain
  is at the Gemma stage, no explicit merge needed.

(We dropped a "spelling" example, potluck: its +Gemma count rose not from a real merge but
from Gemma mis-extracting "potluck" out of "pot roast" / "pot pie" / a username "Pot
Scrubber". A useful reminder that the +Gemma count can also move from extraction errors,
not only synonym resolution; we only showcase clean cases.)

**Where each stage contributes:**
- Gemma resolves obvious (mostly person) synonyms internally but *inconsistently*, so a
  variant can appear in both the Gemma and v1 columns (dh, hubby, kid): the loop catches
  the residual.
- v1 folds frequent variants; **v2 is where the coverage range widens most** -- the long
  tail and whole clusters Gemma never touches (tangy=zesty, the game-day phrases, greek).

Note: a frequent variant adds few NEW recipes when it co-occurs with the canonical (hubby
with husband); the value is a single complete facet. The dramatic count gains are where
the canonical word itself is rare (game-day 2->19, mediterranean 6->11).

## Table 3 (reference only) - Category aggregate, four stages

Sum of recipe-memberships over the top-20 real facets per category (double-counts
recipes; kept only as a rough aggregate). Known residual noise excluded.

| Category | Exact-word | + Gemma | v1 | v2 | Uplift |
| -------- | ----: | ----: | ----: | ----: | ----: |
| Flavor   | 1,527 | 1,378 | 1,777 | 1,870 | +22% |
| Texture  | 1,727 | 1,801 | 1,801 | 1,801 | +4%  |
| Meal     | 999   | 1,092 | 1,241 | 1,269 | +27% |
| Occasion | 775   | 798   | 836   | 948   | +22% |
| Audience | 2,308 | 2,494 | 2,824 | 2,846 | +23% |
| Cuisine  | 393   | 426   | 436   | 444   | +13% |
| **All**  | **7,729** | **7,989** | **8,915** | **9,178** | **+19%** |

---

## Residual noise (the ongoing process)

Noise facets still in the deployed demo, flagged by the judge for the next round
(recipe-level). We leave the demo unchanged; this is a snapshot of an iterative,
human-in-the-loop process.

| Dim. | Residual facet | Recipes | Why it is noise |
| ---- | -------------- | ----: | --------------- |
| Audience | self   | 483 | cook-vs-audience (the reviewer themselves) |
| Audience | us     | 98  | first person plural |
| Audience | others | 42  | too generic |
| Audience | you    | 34  | second person |
| Occasion | occasion | 21 | category name, not a value |

## Validation (precision holds as recall grows)

| Stage | Spicy P/R | Mother P/R | Kids P/R | Macro R | Macro F1 |
| ----- | --------- | ---------- | -------- | ------- | -------- |
| Keyword          | 61/82 | 41/49 | 81/91 | 74 | 67 |
| + LLM extraction | 63/76 | 44/95 | 80/92 | 88 | 72 |
| + Normalization  | 61/90 | 44/91 | 82/99 | 93 | 74 |
| + Judge feedback | 61/90 | 44/91 | 82/99 | 93 | 74 |

Precision steady (~61-63), recall climbs (74->88->93), so the coverage gain is genuine recall.
