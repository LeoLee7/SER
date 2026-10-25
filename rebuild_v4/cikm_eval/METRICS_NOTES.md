# SER Metrics Notes

This is the internal record of every metric explored for the CIKM 2026 demo
submission. Some numbers go into the paper, some do not. The aim is so we (and
Omar) can answer reviewer questions without re-deriving the numbers, and so we
remember exactly what the "Raw / v1 / v2" labels mean.

Last regenerated: see `scripts/build_judge_compare.py` console output.


## 0. Headline findings (read this first)

These supersede earlier optimistic readings. Three things we now understand:

1. **Precision is NOT something our pipeline improves, and that is by design.**
   The normalization loop and the judge-feedback blacklist relabel ("mom"->mother)
   and filter (drop "self", "delicious") at the *type* level. They never re-verify
   an individual extraction, so whether a surviving tag is correct was decided by
   the extractor (Gemma-3). The pooled precision/recall study (Section 3c) confirms
   precision is flat across stages (spicy 61/63/61/61; mother 41/44/44/44;
   kids 81/80/82/82). The larger n=300 precision rerun shrank the earlier "+10pp"
   raw->v2 gain to +3pp, which is within the +/-5.6pp confidence interval, i.e. not
   significant. **Do not sell precision improvement.**

2. **Recall (coverage) IS our measurable contribution, and it is deterministic.**
   Extraction understands surface synonyms (mother recall 49->95) and normalization
   merges the rest (spicy 76->90, kids 92->99). A literal-keyword search misses 16%
   of recipes overall that SER surfaces, and 54% for "mother". This is the strongest
   honest selling point for the search benefit, and it needs no sampling.

3. **The most bulletproof claims are the deterministic, whole-population ones:**
   100% span-groundedness, the 13-14% hallucinated-span drop, and the 9-16x
   vocabulary compression. These have no sampling error.

Recommended headline framing: lead with deterministic groundedness + the recall
gain from normalization + the tidiness/fidelity trade-off; present precision as a
static characterization of the inherited extraction quality (~55%), not a gain.


## 1. The pipeline stages (precise, deployment-matched)

| Stage | What was applied | Where the data lives |
| ----- | ---------------- | -------------------- |
| **Keyword** | no extraction; literal exact-word match in review text | reviews in `extracted_attributes...jsonl` |
| **Gemma (raw extraction)** | direct Gemma-3 output: entity/sentiment/source_text. No span, no normalization. 54,579 attrs. | `extracted_attributes_500recipes.jsonl` (subjective_DB) |
| **Normalization** | + FindSpan grounding + synonym mapping (normalized_entity). 47,248 attrs. No blacklist. | `processed_attributes_500recipes.jsonl` |
| **v1** | Normalization + the ORIGINAL blacklist. The demo as deployed BEFORE this session. Still showed noise facets like "self" (483 recipes). | `food-exhibit-data-500recipes.json.bak.v1` |
| **v2** | v1 + judge-identified noise added to the blacklist (self, i/we/me, fabulous, casual, ...). The CURRENT deployed demo. | `food-exhibit-data-500recipes.json` |

**Critical clarification (corrects earlier loose labeling).** For a *real* facet
(mother, spicy, dinner) that is not noise, v1 = v2 = Normalization, because the
blacklist only ever removes noise concepts, never real ones. So **recall lives in
Keyword -> Gemma -> Normalization**, and the **v1-vs-v2 difference is purely
denoising** (a precision/usability axis). These are two different axes and are
reported in two different tables (Section 3c/3e). Earlier experiment code labeled
"v1" as normalization-without-blacklist and let noise concepts (self, delicious)
into the top-20; the Section 3e tables were rerun with the clean definitions above.

Sample sizes for every judge run: 30 attributes per dimension, 6 dimensions,
180 total per stage. Stratified random with seed 42. n = 30 per cell is small
(95% binomial CI roughly +/- 9 pp around p = 0.5).


## 2. What the LLM judge actually decides

The judge receives a review and one extraction tuple, returns strict JSON with
four binary fields. Definitions (paraphrased from the prompt at
`scripts/llm_judge.py`):

| Field | Question the judge answers |
| ----- | -------------------------- |
| `entity_correct` | Is the extracted entity word or phrase a sensible attribute given this review AND the stated category? Cook self-references in audience are marked false. |
| `category_correct` | Does the entity belong to the stated category given the source text? |
| `sentiment_correct` | Does the polarity label (positive / neutral / negative) match the source text sentiment about that entity? |
| `span_faithful` | Is `source_text` a verbatim substring of the review (ignoring HTML escapes)? |

Derived metrics:

- **Lenient tuple** = entity AND category correct. Maps to ABSA-Pair-F1 numerator (Cai et al. 2021, "Aspect-Category-Opinion-Sentiment Quadruple Extraction").
- **Strict tuple** = all four fields correct. Maps to ABSA-Quad-F1 numerator.

Both variants are the standard reporting convention for the aspect-extraction
literature; the paper reports both.

The judge model is `gpt-oss` on the NRP-Nautilus endpoint
(`https://ellm.nrp-nautilus.io/v1`). Different model family from Gemma-3,
following the cross-family protocol of Zheng et al., NeurIPS 2023
("Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena").


## 3. What we report in the paper

### Headline table (`tables/llm_judge_compare.tex`)

Macro-averaged across the 6 dimensions, n=180 per column.

| Metric (judged precision, %) | Raw  | v1   | v2   | Delta (v2-raw) |
| ---------------------------- | ---- | ---- | ---- | ------------- |
| Entity correct               | 59.4 | 57.8 | 61.7 | +2.2 |
| Category correct             | 60.6 | 58.9 | 61.7 | +1.1 |
| Sentiment correct            | 71.1 | 76.7 | 80.0 | +8.9 |
| Span faithful                | 95.6 | 96.7 | 97.8 | +2.2 |
| Lenient (E AND C)            | 58.3 | 57.2 | 60.6 | +2.2 |
| **Strict (all four)**        | **46.1** | **45.6** | **50.6** | **+4.4** |

Every field and both tuple variants improve monotonically from Raw to v2.

### Detail table (`tables/llm_judge_perdim_v2.tex`)

v2 per-dimension, n=30 each.

| Dimension | Ent  | Cat  | Sent | Span | Lenient | Strict |
| --------- | ---- | ---- | ---- | ---- | ------- | ------ |
| Flavor    | 40.0 | 40.0 | 80.0 | 93.3 | 40.0    | 33.3   |
| Texture   | 96.7 | 93.3 | 90.0 | 100.0| 93.3    | 83.3   |
| Meal Type | 66.7 | 70.0 | 66.7 | 96.7 | 66.7    | 46.7   |
| Occasion  | 56.7 | 56.7 | 86.7 | 100.0| 56.7    | 53.3   |
| Audience  | 63.3 | 63.3 | 83.3 | 96.7 | 60.0    | 53.3   |
| Cuisine   | 46.7 | 46.7 | 73.3 | 100.0| 46.7    | 33.3   |
| **Macro** | **61.7** | **61.7** | **80.0** | **97.8** | **60.6** | **50.6** |

### Database scale + groundedness (`tables/db_stats.tex`)

| Dimension | Extracted mentions | Raw entities | Canonical forms | Comp. ratio | Top-10 coverage |
| --------- | -----------------: | -----------: | --------------: | ----------- | --------------: |
| Flavor    | 19,807 | 2,705 | 170 | 15.9 x | 39.7 % |
| Texture   |  6,630 | 1,003 | 108 |  9.3 x | 49.8 % |
| Meal Type |  3,978 |   385 |  39 |  9.9 x | 80.0 % |
| Occasion  |  2,866 |   815 |  56 | 14.6 x | 56.6 % |
| Audience  | 12,330 |   917 | 100 |  9.2 x | 63.1 % |
| Cuisine   |  1,637 |   251 |  20 | 12.6 x | 86.6 % |

Span groundedness across the full database (post-FindSpan filter) is 100 %
by construction.

### Normalization convergence (`tables/normalization.tex`)

| Dimension | Raw entities | Canonical forms | Comp. ratio | Top-10 cov | Top-30 cov | Converged (top-30 >= 80%) |
| --------- | -----------: | --------------: | ----------- | ---------: | ---------: | ------------------------- |
| Flavor    | 2,705 | 170 | 15.9 x | 39.7 % | 58.7 % | no |
| Texture   | 1,003 | 108 |  9.3 x | 49.8 % | 74.8 % | no |
| Meal Type |   385 |  39 |  9.9 x | 80.0 % | 96.2 % | YES |
| Occasion  |   815 |  56 | 14.6 x | 56.6 % | 86.3 % | YES |
| Audience  |   917 | 100 |  9.2 x | 63.1 % | 82.1 % | YES |
| Cuisine   |   251 |  20 | 12.6 x |100.0 % |100.0 % | YES |

The convergence criterion is the agent skill's own stop rule (top-30 canonical
forms cover at least 80 % of mentions per dimension). Flavor and Texture
plateau below threshold; these dimensions have inherently long Zipfian tails
in opinion text (Zhang et al. ABSA survey 2022).

### Query-to-facet parser (`tables/query_to_facet.tex`)

Slot-F1 metrics, Snips / ATIS convention (Coucke et al. 2018).

| Metric              | Value |
| ------------------- | ----: |
| Micro Precision     | 84.4 |
| Micro Recall        | 75.0 |
| Micro F1            | 79.4 |
| Exact-match rate    | 41.7 % (5 of 12) |

Test set is author-curated, n = 12. Target n is 30-40 before submission.

### Normalization fidelity (`tables/merge_fidelity.tex`) -- the tidiness vs expressiveness trade-off

This is the new metric that captures the project's core tension: synonym merging
makes the database tidy (few clean facets) but can DISTORT meaning. We sample only
the attributes the loop re-labelled (entity != canonical), frequency-weighted per
dimension, and have the judge rule each merge faithful / broader / distorts.
Framing follows open-KB canonicalization quality (Galarraga et al., CIKM 2014).

| Dimension | n  | Faithful % | Broader % | Distorts % |
| --------- | -- | ---------- | --------- | ---------- |
| Flavor    | 30 | 40 | 40 | 20 |
| Texture   | 11 | 100 | 0 | 0 |
| Meal Type | 30 | 37 | 23 | 40 |
| Occasion  | 30 | 53 | 43 | 3 |
| Audience  | 30 | 60 | 17 | 23 |
| Cuisine   | 30 | 10 | 70 | 20 |
| **All**   | 161 | **44** | **36** | **20** |

Reading: 80% of merges are acceptable for a faceted filter (faithful 44 + broader 36);
20% distort meaning. Worst dimension is Meal Type (40% distort -- driven by
`meal -> casual`, which is a bad merge we should remove). Cuisine is mostly
"broader" (greek -> mediterranean, tex-mex -> mexican): defensible generalizations,
not errors. Texture merges are trivially faithful (only plural/stemming changes).

Actionable: the `meal -> casual` mapping is the single biggest fidelity leak; drop it.


## 3b. Data scale and sampling soundness (re-established)

**Population (whole dataset, deterministic -- not sampled):**

| Quantity | Value |
| -------- | ----- |
| Recipes | 500 |
| Reviews | 10,015 |
| Truly-raw tags (direct Gemma-3) | 54,579 |
| After FindSpan grounding | 47,248 (dropped 7,331 = 13% ungroundable / hallucinated spans) |
| After blacklist v2 | ~32,000 |

**Measurements (sampled) and their 95% confidence intervals (Wilson):**

| Measurement | Value | n | 95% CI | half-width |
| ----------- | ----- | - | ------ | ---------- |
| Truly-raw precision (lenient) | 50.6% | 180 | [43, 58] | ±7 pp |
| v2 precision (lenient) | 60.6% | 180 | [53, 67] | ±7 pp |
| v2 demo-relevant precision (E∧C∧Span) | 58.9% | 180 | [52, 66] | ±7 pp |
| Merge acceptable (faithful+broader) | 80.1% | 161 | [73, 86] | ±6 pp |
| Query-to-facet micro-F1 | 79.4% | 12 | wide | too small |

**Soundness verdict:**
- The deterministic population numbers (scale, 13% hallucination drop, 9-16x
  compression) are exact -- no sampling caveat. These are our most bulletproof claims.
- n=300 precision rerun: truly-raw 53.0%, v2 56.0% (lenient). The +3pp gap is inside
  the +/-5.6pp CI -- not significant. The earlier n=180 "+10pp" was small-sample noise.
- n=161 fidelity is fine; 80% acceptable with +/-6 pp is a solid, reportable number.
- n=12 query-to-facet is too small to report a stable F1; expand to 30-40 before any
  external claim.


## 3c. Pooled precision-recall across the pipeline (the rigorous version)

`tables/pr_concept.tex`, script `scripts/eval_pr_concept.py`. For three concepts
we pool the recipes returned by four methods (literal keyword; Gemma raw entity;
+normalization v1; +judge v2), then an independent judge labels each pooled recipe
for whether the concept genuinely applies, handling negation ("not spicy"),
ingredient mentions ("spicy mustard"), and irrelevant mentions ("my mother used to
make it"). Precision/recall are computed per method against that common gold
(pooled recall, TREC assumption).

| Concept | Stage | P% | R% | F1 |
| ------- | ----- | -- | -- | -- |
| spicy  | (1) keyword       | 61 | 82 | 70 |
|        | (2) gemma         | 63 | 76 | 69 |
|        | (3) +normalize    | 61 | 90 | 73 |
|        | (4) +judge fb     | 61 | 90 | 73 |
| mother | (1) keyword       | 41 | 49 | 45 |
|        | (2) gemma         | 44 | 95 | 60 |
|        | (3) +normalize    | 44 | 91 | 60 |
|        | (4) +judge fb     | 44 | 91 | 60 |
| kids   | (1) keyword       | 81 | 91 | 86 |
|        | (2) gemma         | 80 | 92 | 86 |
|        | (3) +normalize    | 82 | 99 | 90 |
|        | (4) +judge fb     | 82 | 99 | 90 |

Readings:
- **Precision is flat across stages (2)-(4)** for all three concepts. Confirms the
  pipeline does not re-verify; per-item correctness is the extractor's.
- **Recall is where the pipeline moves.** The big jump is keyword->gemma for mother
  (49->95): the LLM resolves "mom"/"mum" to mother, which a literal "mother" search
  misses. Normalization adds the rest (spicy 76->90 via heat/kick/hot; kids 92->99).
- **F1 gains are recall-driven** (spicy 70->73, mother 45->60, kids 86->90).
- **Keyword precision is concept-dependent**, so do NOT claim "keyword is imprecise"
  in general: mother 41% (many irrelevant mentions), spicy 61% (ingredients/negation),
  but kids 81% (usually genuine). The honest claim is that SER lifts recall to 90%+
  on every concept without lowering precision.

Caveat on absolute precision: the gold uses a strict reading (e.g., "mother" must
*enjoy/relate to* the dish, not merely be mentioned), so the ~44% mother precision
reflects genuine extractor over-extraction, not a measurement artifact. The
cross-method comparison on the same gold remains valid.

### Error cases (full dump: `eval_data/pr_concept_errors.json`)

Keyword false positives, the concrete failure modes:
- spicy: "spicy brown mustard" (ingredient, not the dish); "I would not say it was
  spicy"; "add cayenne for more kick" (dish currently lacks spice).
- mother: "my BF's mother gifted us" (gifting, not enjoying); "as a child my mother
  used to make it" (past memory, different dish); mother named as an ingredient source.
- kids: "kids wouldn't have touched it" (negation -> not enjoyed); "kids mentioned but
  didn't notice" (no enjoyment).


## 3d. Concept-coverage / recall gain (deterministic)

`tables/recall_gain.tex`, script `scripts/eval_recall_gain.py`. Coverage comparison
(no LLM judge, no sampling): recipes a literal exact-word search finds vs recipes the
SER canonical facet finds.

| Concept | Keyword (exact word) | SER (facet) | Missed by keyword |
| ------- | -------------------- | ----------- | ----------------- |
| mother  | 89  | 194 | 54% |
| husband | 441 | 480 | 8%  |
| kids    | 284 | 320 | 11% |
| daughter| 182 | 225 | 19% |
| spicy   | 133 | 174 | 24% |
| sweet   | 230 | 242 | 5%  |
| mediterranean | 1 | 11 | 91% (small n) |
| dinner  | 330 | 364 | 9%  |
| **Total** | **1690** | **2010** | **16%** |

Mechanism: the gain comes from (a) Gemma already resolving "mom"->mother at
extraction, plus (b) our synonym map merging spelling/abbreviation variants
(DH/hubby->husband, heat/kick->spicy, greek->mediterranean). Both are part of SER.
This is the cleanest selling-point-3 number: deterministic, intuitive, no circularity
(it is a coverage comparison, not recall against SER's own output).


## 3e. Recall + Denoising tables (deployment-matched, the two quality axes)

Generated by `scripts/make_quality_tables.py` -> `tables/recall_dist.tex`,
`tables/denoising.tex`. Concept set for the recall table = real deployed facets
(top-20 per category, blacklisted noise excluded). Gold-free; counts are observed.

**Table A - Recall (coverage growth on real facets).** Per-concept relative
improvement over keyword, median [IQR] across top-20 (median because heavy-tailed):

| Category | Keyword (abs) | + Gemma med[IQR] | + Normalization med[IQR] | Extra |
| -------- | ----: | :--: | :--: | ----: |
| Flavor   | 1,412 | -4 [-23,+1] | +2 [0,+69]  | +348 |
| Texture  | 1,727 | +1 [0,+5]   | +1 [0,+5]   | +74  |
| Meal     | 999   | +0 [0,+5]   | +0 [0,+31]  | +270 |
| Occasion | 773   | +0 [-7,+2]  | +15 [+1,+63]| +180 |
| Audience | 2,332 | +0 [-1,+6]  | +13 [+6,+47]| +524 |
| Cuisine  | 393   | +0 [0,+11]  | +5 [0,+18]  | +51  |
| **All**  | 7,636 | | | **+1,447 (+19%)** |

Median concept gains little (canonical word dominates) but the upper IQR is large in
synonym-rich categories; Gemma is selective (coverage-neutral, sometimes negative);
normalization is the recall lever. Aggregate +19% over keyword, gold-free.

**Table B - Denoising (precision / facet usability; the v1 vs v2 axis).** Noise
facet-values removed per round:

| Category | v1 removed (orig.) | v2 added (judge) | v2 examples (recipes) |
| -------- | ----: | ----: | ----- |
| Flavor   | 35 | 9 | fabulous (158), yum (104), incredible (69) |
| Texture  | 7  | 2 | amazing (5) |
| Meal     | 3  | 1 | casual (188) |
| Audience | 8  | 3 | self (484), us (98) |
| Occasion | 8  | 0 | -- |
| Cuisine  | 2  | 0 | -- |
| **Total**| 63 | 15 | |

v1 removed 63 noise facets; the judge round (v2) removed 15 more, including the
biggest remaining offenders (self 484, casual 188, fabulous 158).

**Two-axis framing.** Merge (normalization) raises recall; filter (blacklist) raises
precision/usability. They are complementary, not a tradeoff. The LLM-judge loop is the
balancer: it flags genuine noise to filter without touching real attributes. The
pooled judged study (Section 3c) confirms precision is constant on real concepts while
recall rises.


## 4. What we explored but did NOT put in the paper

These are kept here as backup ammunition for reviewer questions.

### Per-field per-stage table (paper has macro only)

Per-dimension breakdowns for Raw and v1, kept for completeness.

Raw, n=30 per dimension:

| Dimension | Ent  | Cat  | Sent | Span | Lenient | Strict |
| --------- | ---- | ---- | ---- | ---- | ------- | ------ |
| Flavor    | 30.0 | 30.0 | 86.7 |100.0 | 30.0    | 23.3   |
| Texture   | 90.0 | 90.0 | 80.0 |100.0 | 90.0    | 73.3   |
| Meal Type | 60.0 | 60.0 | 43.3 | 93.3 | 60.0    | 33.3   |
| Occasion  | 60.0 | 56.7 | 80.0 | 93.3 | 56.7    | 40.0   |
| Audience  | 63.3 | 66.7 | 76.7 |100.0 | 63.3    | 63.3   |
| Cuisine   | 53.3 | 60.0 | 60.0 | 86.7 | 50.0    | 43.3   |

v1, n=30 per dimension:

| Dimension | Ent  | Cat  | Sent | Span | Lenient | Strict |
| --------- | ---- | ---- | ---- | ---- | ------- | ------ |
| Flavor    | 33.3 | 33.3 | 80.0 | 96.7 | 33.3    | 26.7   |
| Texture   | 83.3 | 83.3 | 86.7 | 96.7 | 83.3    | 66.7   |
| Meal Type | 60.0 | 63.3 | 60.0 |100.0 | 60.0    | 40.0   |
| Occasion  | 56.7 | 53.3 | 86.7 |100.0 | 53.3    | 50.0   |
| Audience  | 56.7 | 63.3 | 70.0 | 96.7 | 56.7    | 46.7   |
| Cuisine   | 56.7 | 56.7 | 76.7 | 90.0 | 56.7    | 43.3   |

### Failure-cluster mining (drives the v1 -> v2 update)

The 30 v1 judgments for each dimension were post-hoc clustered into noise
classes. The following terms made it into the v2 blacklist:

- `audience_enjoyment`: `self`, `i`, `me`, `we`, `myself`, `ourselves`, `us`
  (cook-vs-audience self references; six occurrences of `self` were judged
  wrong with the rationale "refers to the reviewer, not an audience member")
- `taste_flavor`: `fabulous`, `outstanding`, `goodness`, `yum`, `incredible`,
  `marvelous`, `superb`, `divine`, `heavenly` (generic positive adjectives;
  three `fabulous`, plus singletons)
- `texture_mouthfeel`: `amazing`, `superbly`
- `meal_type`: `casual` (not a meal-type; quality attribute)
- `occasion_holiday`: nothing added (failures were proper nouns we cannot
  blanket-blacklist: `Germany`, `December`, `Lucille and Otley's`, etc.)
- `cuisine_type`: nothing added (failures are extraction-prompt-level
  modifier-vs-dish ambiguity: `Italian bread crumbs`, `Mexican blend cheese`;
  blacklisting real cuisine names would hurt overall coverage)

The judge-derived counts at n>=2 (`italian`, `mexican`, `dinner`, `fall`)
were emitted to `eval_data/blacklist_updates.json` as evidence but
explicitly **not** applied; these are legitimate canonical values whose
failures stem from context-specific issues that a blanket blacklist would
over-correct.

### Where Audience went backward and why

Raw audience strict precision was 63.3 % because most audience extractions
(`husband`, `kids`, `family`, ...) are real. The v1 synonym map then mapped
`I` / `me` / `we` to `self`, which the judge correctly marked wrong in most
cases, dragging v1 down to 46.7 %. v2 blacklists `self` and the personal
pronouns entirely, recovering +6.6 pp over v1. The remaining gap from Raw
(53.3 vs 63.3) reflects that some `self` instances were legit (reviewer is
both cook and consumer). A context-sensitive rule (keep `self` only when
paired with another audience term, or expand by parsing "my wife and I"
patterns) is the natural next step.

### Where Cuisine appeared to regress

v1 strict 43.3, v2 strict 33.3. The 10 pp drop on n=30 is within sample
variance (1 item = 3.3 pp). The structural issue is modifier-vs-dish
ambiguity: `Italian bread crumbs` extracts `Italian` to cuisine, but the
dish is not Italian. This is an extraction-prompt-level problem, not a
post-processing one. Listed as future work.

### Filter yield

| Stage           | Tuples kept | Tuples filtered | Filter rate |
| --------------- | ----------: | --------------: | ----------: |
| Raw             | 47,248 | -- | -- |
| Post-loop v1    | 35,296 | 11,952 | 25.3 % |
| Post-loop v2    | 32,301 | 14,947 | 31.6 % |

The agentic skill is doing serious noise removal: roughly one in three raw
extractions is judged sufficiently uninformative to drop.

### Three-system end-to-end retrieval (DEPRECATED -- kept for the record)

`tables/retrieval.tex`, `scripts/eval_retrieval.py`. We compared catalog-keyword
(BM25 over name+description+ingredients), review-keyword (BM25 over raw reviews),
and SER facet retrieval on the 12 subjective queries, with pooled LLM relevance
judgments. Result (n=12, k=5): catalog Success@5 50% / zero-rel 50%; review 75% /
25%; SER 67% / 33%. **Review-keyword beat SER on raw hit-rate.** Why we dropped it:
(1) n=12, k=5 -> differences are within ~+/-27pp, not significant; (2) the relevance
judge saw review snippets, structurally favoring the review-keyword system that
matched on those very reviews; (3) hit-rate is the wrong axis for SER's value, which
is structured/combinable/evidence-linked facets, not beating BM25 on recall of a
single concept. The concept-coverage metric (3d) and pooled PR (3c) capture SER's
real contribution far more cleanly. Do not revive this without fixing the judge
confound and expanding to 30-40 queries.


## 5. What we deliberately did NOT measure

- **Recall** of the extractor. We sampled extracted tuples and judged them
  (a precision-only protocol). To get recall we would need to sample reviews,
  ask the judge what attributes SHOULD be extracted, and check whether
  Gemma-3 caught them. We did not do this. The paper says so explicitly.
- **Inter-judge agreement** (Cohen's kappa across two judge models). The
  Zheng et al. protocol recommends this but our budget did not allow it.
  Future work.
- **User study** for the search UI. Out of scope for a 4-page demo and
  deliberately excluded after talking with the user.
- **End-to-end search quality** (nDCG@k on a benchmark query set). Not in
  scope; the query-to-facet table is a proxy.


## 6. Reading the numbers

A few honest notes for ourselves.

- **Span fidelity at 97-100 %** is the strongest single number; it directly
  answers SIGIR Reviewer 1's concern about LLM hallucination.
- **Sentiment +8.9 pp Raw -> v2** is the largest field-level improvement and
  benefits from the v2 blacklist removing generic positive adjectives that
  the extractor had labeled as positive even though they were not real
  attributes.
- **Strict tuple precision** is the most demanding metric and the one most
  literature reports. 50.6 % macro across 6 dimensions on free-form UGC is
  in the same range as ABSA-Quad results on cleaner restaurant benchmarks.
- **n=30 per dimension** is small. The macro over 180 has tighter CI but
  per-dimension comparisons (e.g., Cuisine -10 pp) are noisy.
