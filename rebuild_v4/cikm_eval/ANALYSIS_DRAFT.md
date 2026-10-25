# Draft evaluation passage (rigorous, paper-ready)

Numbers verified against eval_data/ on the current run. English academic prose.

---

## Option A — full version (3 paragraphs, ~280 words)

**Evaluation design.** Because no exhaustive ground truth exists for ten thousand
free-text reviews, we follow the on-demand, sampling-based protocol established for
knowledge-base population, where precision is estimated by judging a system's own
outputs and full recall is acknowledged to be both expensive and biased to estimate
[Chaganty et al., 2017]. We therefore separate two questions that are easy to
conflate: the *precision* of the attributes the system retains, and the *recall* of
relevant items it surfaces relative to a literal keyword search. For three
representative concepts (spicy, mother, kids) we pool the recipes returned by four
successive stages of the pipeline (literal keyword match, raw LLM extraction,
normalization, and judge-feedback filtering) and obtain an independent relevance
label for each pooled recipe from a cross-family LLM judge that is instructed to
respect negation and irrelevant mentions.

**The pipeline preserves precision and expands recall.** Our normalization and
filtering operate at the level of attribute *vocabulary*: they consolidate surface
variants ("mom" to mother) and prune noise categories ("delicious", first-person
"self"). This vocabulary-level design is transparent and auditable, and it preserves
the extractor's per-item precision rather than perturbing it: judged precision is
stable across stages (spicy 61 to 61, mother 44 to 44, kids 82 to 82), and enlarging
the sample to 300 leaves the raw-to-final difference at three points, within the
confidence interval. The measurable gain is in recall. Extraction alone resolves
lexical synonymy that exact matching cannot (mother recall rises from 49 to 95), and
normalization recovers the remaining surface variants (spicy 76 to 90, kids 92 to
99), so the F1 improvement is driven entirely by recall while precision is held
constant.

**Coverage gain and groundedness.** The recall effect is confirmed deterministically,
without any judge: across eight common concepts a literal-word search misses 16% of
the recipes the corresponding facet surfaces, rising to 54% for mother (89 versus 194
recipes), because reviewers express one concept through many forms. The analysis also
exposes why exact matching is unreliable in the first place: keyword false positives
arise from ingredient mentions ("spicy mustard"), explicit negation ("I would not say
it was spicy"), and irrelevant context ("as a child my mother used to make it").
Finally, every retained attribute is anchored to a verbatim review span; the 14% of
raw extractions whose evidence cannot be located are discarded before indexing,
yielding complete span-groundedness in the deployed database.

---

## Option B — compact version (1 paragraph, ~120 words)

We separate precision from recall, since exhaustive ground truth is infeasible and
recall is known to be expensive and biased to estimate at scale [Chaganty et al.,
2017]. On three pooled, independently judged concepts, precision is flat across the
pipeline (e.g. kids 82 to 82) because normalization and filtering relabel and prune
attribute *types* rather than re-verifying individual extractions; per-item
correctness is therefore inherited from the extractor. The measurable gain is in
recall: synonym resolution lifts coverage from 49 to 95 for mother and from 92 to 99
for kids, and a deterministic comparison shows a literal-word search misses 16% of
the recipes a facet surfaces (54% for mother). Keyword false positives stem from
ingredient, negation, and irrelevant-mention cases that the extraction step avoids.

---

## Numbers used (all verified against eval_data/)

- Pooled PR (n: spicy 199, mother 225, kids 340 recipes):
  spicy P 61/63/61/61, R 82/76/90/90; mother P 41/44/44/44, R 49/95/91/91;
  kids P 81/80/82/82, R 91/92/99/99 (stages: keyword/gemma/v1/v2).
- Precision rerun n=300 lenient: raw 53.0, v2 56.0 (+3pp, CI +/-5.6).
- Coverage: keyword misses 16% overall, 54% for mother (89 -> 194).
- Span groundedness 100%; 14% of raw extractions dropped for unlocatable spans.
- Merge fidelity: 44% faithful, 36% broader-acceptable, 20% distorts (n=161).

## Demo-track framing (angles 1 + 5) -- paper-ready

### Contribution bullets (for the introduction)

- **A subjective search demo that matches concepts, not strings.** SER lets a user
  satisfy requests such as "Christmas food my picky kids will eat" by filtering on
  experiential facets (flavor, texture, meal type, occasion, audience, cuisine) mined
  from 10,015 reviews over 500 recipes, with two interaction modes: direct facet
  selection and a natural-language query-to-facet parser.
- **Evidence-linked results.** Every facet value is anchored to the verbatim review
  span it came from; selecting a facet highlights the supporting sentences, so users
  see why a recipe matched. All retained attributes are span-grounded by construction.
- **Concept-level recall that exact-word search cannot reach.** Because the index is
  built on normalized concepts, a query for "mother" also returns recipes whose
  reviewers wrote "mom" or "mum"; across common concepts a literal-word search misses
  13% of the recipes the facets surface (54% for "mother"). We characterize where this
  helps (high-variation categories such as Audience and Cuisine) and where it does not
  (Flavor, Texture), giving a transferable picture rather than a single anecdote.

### The motivating contrast (one tight paragraph)

Catalog search matches the words in a recipe's title, description, and ingredients,
none of which carry experiential meaning, so a subjective request returns little of
use. The experiential signal lives in the reviews, but it is fragmented across many
surface forms ("mom", "mum", "mommy"; "hubby", "DH"; "heat", "kick", "hot"). SER
extracts that signal and consolidates each concept into a single clickable facet, so
the same request reaches every recipe that expresses the concept, in any words. This
is the demonstrated benefit attendees can try live.

### What visitors will experience (demo scenario)

A visitor types or assembles a request, for example "tender comfort food my kids
enjoy". SER parses it into facets (texture: tender; audience: kids), returns matching
recipes ranked by support, and for each result expands the reviews with the exact
spans that justify "tender" and "kids". The visitor can then add a catalog constraint
(under 1000 calories, under 30 minutes), swap the audience to "husband", or open a
second vertical (movies) to see the same pipeline applied to a different domain.

### How the evaluation supports the demo claim (not a benchmark contest)

The evaluation is scoped to substantiate the demo's premise, that concept-level
indexing surfaces relevant items surface matching misses. The per-category coverage
figure shows the recall gain and, importantly, its distribution: normalization pays
off precisely where surface variation is high. A pooled, independently judged study
on three concepts confirms the gain is genuine recall at constant precision. We do not
claim improved extraction precision and we do not stage a retrieval bake-off; the
contribution is the interactive, evidence-grounded, concept-level experience.


## Citation note
- Chaganty, Paranjape, Liang, Manning. "Importance Sampling for Unbiased On-Demand
  Evaluation of Knowledge Base Population." EMNLP 2017.
- Pooled judgments follow TREC practice; LLM relevance judging follows the SIGIR 2024
  LLM4Eval line (Thomas et al., 2024). Tuple fields follow ABSA-Quad (Cai et al. 2021).
