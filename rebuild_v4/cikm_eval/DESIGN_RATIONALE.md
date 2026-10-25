# SER: staged design rationale (synthesis of our evolved thinking)

> ## ★ CORE THESIS (the global framing — keep consistent everywhere) ★
> SER's quality rests on **two pillars**:
> - **Precision is evidence-led**: every facet value traces to a verbatim review span
>   (98-100% traceable; 100% at DB level), plus context-aware extraction that avoids the
>   negation/off-topic false positives literal keyword search returns.
> - **Recall is grouping-led**: synonym normalization merges scattered surface variants
>   into one clean facet (+19% coverage over keyword search).
>
> "Precision has no advantage" applies **only** to the v1->v2 normalization round (no
> per-item delta); it does NOT mean SER lacks a precision contribution — extraction and
> evidence-grounding deliver that. Do not understate it.
> (Also carved into project memory: `ser-two-pillars-positioning`.)

The reusable record of WHY the pipeline is staged the way it is, what each stage buys,
and where each falls short. Distilled from the discussion that shaped the paper.

---

## The core idea (one paragraph)

SER turns the messy, free-text opinions in reviews into clean, clickable facets. The
hard part is not extraction alone but *organizing* the extracted attributes: the same
idea is written many ways ("mom"/"mum", "DH"/"hubby", "tangy"/"tart"/"zesty"), and a lot
of what is extracted is non-discriminative noise ("delicious", "self"). We handle this
with a staged, human-in-the-loop normalization process, and we are deliberate that it
moves two *different* quality axes:

- **Recall / coverage** is carried by **grouping** (synonym consolidation): a user finds
  recipes they would otherwise miss.
- **Precision** is carried mainly by **evidence-grounding** (every tag must trace to a
  verbatim review span) plus context-aware extraction (the LLM avoids negation/off-topic
  matches); **filtering** (blacklist) additionally keeps the facets clean and usable.

These are complementary, not a trade-off against each other.

**Important scoping.** When we say the agentic normalization "does not improve
precision", we mean only the v1->v2 normalization *round*: it relabels and filters at the
type level and does not re-verify individual extractions, so it adds no per-item precision
delta. SER as a whole DOES contribute precision -- through context-aware extraction and,
above all, the evidence-grounding requirement (98-100% of tags trace to text, 100% at the
DB level). Precision is an evidence-led contribution, not a per-round metric gain, and we
do not understate it.

---

## The staged design (what each stage does / its benefit / its limitation)

| Stage | What it does | Benefit | Limitation |
| ----- | ------------ | ------- | ---------- |
| **Gemma extraction** | Pulls subjective attributes from free text; resolves the obvious, high-frequency (mostly person) synonyms internally while reading (writes "mother" for "my mom") | Turns unstructured UGC into typed, span-grounded attributes; gives bulk synonym resolution for free | Selective (misses some genuine mentions); inconsistent (resolves a variant in some reviews, leaves it raw in others); can mis-extract (tags "potluck" from "pot roast") |
| **v1 - normalization, round 1** | Merges the frequent residual synonym variants the extractor left inconsistent; blacklists the obvious noise; observes frequency-sorted counts | Cheap and fast; completes the high-frequency head of each facet; removes the worst noise | Misses the long tail and multi-word phrases; a single pass |
| **v2 - convergence + judge feedback** | Merges the rare and phrasal long-tail variants; removes residual noise that the independent LLM judge flags | Widens coverage to rare/phrasal synonyms (greek->Mediterranean, the game-day phrases); cleanup is judge-targeted, not guesswork | Still not exhaustive (residual noise such as "self" remains); needs a judge; the process is ongoing |

Reading the gradient: extraction does the obvious synonyms, v1 the frequent residual,
v2 the long tail. Each stage recovers cases the others cannot (e.g. the *game-day* facet
exists only after v2 merges super bowl / football game / game night).

---

## Cross-cutting design choices

| Choice | Why |
| ------ | --- |
| **Human-or-agent dial** | Each normalization step can be run by a person (high-stakes domains) or by the agent (scale). Controls quality and limits hallucination; not all-or-nothing. |
| **Evidence-led precision; precision-preserving loop** | Precision is delivered by context-aware extraction and the evidence-grounding requirement (every tag traces to a span). The normalization loop on top relabels/filters at the type level and never re-verifies, so the loop itself adds no precision delta (judged precision flat across the v1->v2 round) -- but SER's precision contribution is real and lives in extraction + evidence, not in a per-round gain. |
| **Iterative, never "finished"** | The deployed v2 is a snapshot of an ongoing process. Residual noise is expected and is the next round's target, not a defect to hide. |
| **Evidence-grounded** | Every facet value keeps its source span, so results are explainable and nothing is invented. |

---

## Honest limitations (what we say up front)

- **No recall against a gold set.** We have no exhaustive hand-labeled answer key, so we
  report coverage gain over keyword search (deterministic) and validate quality on a
  judged sample; we do not claim a true recall percentage.
- **Precision is moderate and inherited** (~half to two-thirds of tags correct, varying
  by category); the pipeline does not, and is not meant to, raise it.
- **Extraction errors propagate** (e.g. "potluck" from "pot roast"); the loop filters
  many but not all.
- **Residual noise remains in the deployed demo** ("self" as an audience facet); on
  narrative, since the process is iterative.
- **Coverage gain is concentrated**, not uniform: large for synonym-rich concepts and
  categories (Audience, Cuisine, Occasion), near zero where reviewers already write the
  canonical word (much of Flavor, Texture).

---

## Why this design is good (the strengths to lead with)

These are the angles that survived the discussion as the strongest, honest selling
points. They are framed for a demo paper.

1. **Concept-level search, not string matching.** Traditional search matches the words
   in a recipe; SER matches the *concept*. A query for "mother" also returns recipes
   whose reviewers wrote "mom"/"mum"; a query for "game-day" returns "super bowl"/
   "football game" recipes. The benefit is largest exactly where surface variation is
   high (Audience, Cuisine, Occasion) and is something exact-word search can never do.

2. **Evidence-led precision.** SER's precision comes from two sources that are core
   parts of the system: context-aware extraction (the LLM avoids the negation/off-topic
   matches that trip up literal search) and, above all, the evidence-grounding
   requirement -- every facet value must trace to a verbatim review span (98-100%
   traceable; 100% at the DB level). The normalization round on top is precision-preserving
   (type-level relabel/filter, no per-item delta), which is why it shows no precision
   gain -- but that does not diminish the precision the extraction and evidence stages
   deliver. The contribution is clean, combinable, evidence-linked facets.

3. **An honestly quantified trade-off.** Most normalization work reports only benefits.
   We measure both sides: the coverage gain from merging *and* the fidelity cost (what
   fraction of merges preserve meaning), and we audit individual merges. We even surface
   the failure modes (Gemma mis-extraction, residual noise) rather than hiding them.

4. **A transferable insight, not just a demo.** The per-category analysis shows *where*
   normalization pays off (synonym-rich categories) and where it does not (categories
   whose canonical word is what people already type). That is guidance future
   practitioners can reuse.

5. **A live, evidence-grounded artifact.** Faceted + natural-language search with
   span-highlighted evidence; 100% of facet values trace to a verbatim review span, a
   direct answer to the LLM-hallucination concern. The same skill runs across food and
   movie verticals (cross-domain portability), and each quality step offers a human or
   agent mode (the human-or-agent dial).

---

## IR / literature support (what grounds each design and metric choice)

| Design / metric choice | Grounded by | What it justifies |
| ---------------------- | ----------- | ----------------- |
| Report **precision, not recall**, by sampling system output | Chaganty, Paranjape, Liang, Manning, "Importance Sampling for Unbiased On-Demand Evaluation of KBP", EMNLP 2017 | Without an exhaustive gold, recall is expensive and biased to estimate; sampling outputs and judging them is the accepted protocol |
| **Tuple-level P/R/F1**, strict (all fields) vs lenient (entity+category) | Cai, Xia, Yu, "Aspect-Category-Opinion-Sentiment Quadruple Extraction", ACL 2021 (ABSA-Quad) | Our (category, entity, sentiment, span) tuples mirror ABSA quadruples; strict/lenient are the standard reporting variants |
| Long-tail / Zipfian behavior of opinion vocab; ABSA framing | Zhang, Li, Deng, Bing, Lam, "A Survey on Aspect-Based Sentiment Analysis", IEEE TKDE 2022 | Why Flavor/Texture have long tails that plateau below the coverage threshold |
| **LLM-as-a-judge**, cross-family to cut self-preference bias | Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", NeurIPS 2024 | Using gpt-oss (different family) to judge Gemma-3 extractions |
| **Span faithfulness / groundedness** as an anti-hallucination metric | Honovich et al., "TRUE: Re-evaluating Factual Consistency Evaluation", NAACL 2022 | Reporting verbatim-span grounding; strong model as silver reference |
| **Synonym canonicalization quality / cluster precision** | Galarraga et al., "Canonicalizing Open Knowledge Bases", CIKM 2014 | The merge-fidelity metric (faithful / broader / distorts); CIKM's own topic |
| **Slot-filling evaluation** (slot-F1, exact-match) for query->facet | Coucke et al., "Snips Voice Platform", arXiv 2018 | Evaluating the natural-language query-to-facet parser |
| **Faceted-search usability**; few clean facets; top-k coverage | Hearst, "Search User Interfaces" (Ch. 8), Cambridge Univ. Press 2009 | Why the blacklist matters (clean, discriminative facets) and the 80% top-k convergence criterion |
| **nDCG** and rank-aware retrieval metrics | Jarvelin & Kekalainen, "Cumulated gain-based evaluation of IR techniques", ACM TOIS 2002 | The (set-aside) retrieval comparison metrics |
| **LLM relevance judgments** + **TREC pooling** | Thomas et al., SIGIR 2024 (LLMJudge / LLM4Eval); Voorhees (TREC) | Pooled, LLM-judged relevance for the retrieval study |
| **Relative improvement over baseline / lift / base-100 index** | Tan, Steinbach, Kumar, "Introduction to Data Mining" (lift) | The relative-uplift / index-to-keyword presentation |
| **Agentic loop / skill** | Yao et al., "ReAct", ICLR 2023; Anthropic Agent Skills, 2025 | The observe-verify-update normalization skill |

Bib entries for the items already cited in the paper live in `references2.bib`
(zheng2024judging, cai2021aspect, zhang2022survey, honovich2022true, coucke2018snips,
hearst2009search, yao2023react, anthropic2025skills, openai2025gptoss). The remaining
ones (Chaganty 2017, Galarraga 2014, Jarvelin 2002, Thomas 2024) are added when their
section enters the paper.

---

## How this maps to the paper's contributions

1. The subjective facets (six experiential dimensions from reviews).
2. The staged, human-or-agent normalization that organizes them (this document).
3. The demo: faceted + natural-language search with evidence highlighting, letting users
   satisfy subjective requests that keyword search handles poorly.
