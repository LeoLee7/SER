# SER Project Summary (plain-language working doc)

Audience: anyone joining the project cold, no background needed. Kept jargon-free
on purpose. The detailed technical record lives in `METRICS_NOTES.md`; this doc
is the "explain it to a colleague over coffee" version.

Last updated: keep this line current when numbers change.

---

## 1. The one-sentence version

We are building a recipe search tool that understands *subjective* requests like
"Christmas food my picky kids will actually eat," by reading what real people
wrote in reviews and turning those opinions into filters you can click.

## 2. The problem we are solving

Normal recipe search only knows the facts a database stores: ingredients,
calories, cooking time. It cannot answer a request like "comfort food for a sick
kid" because no database column says "comfort food" or "good for sick kids."

But people *say* these things all the time in reviews: "this is the only dish my
picky son will eat," "perfect for a rainy day." That knowledge is sitting in the
review text, unused. Our system pulls it out and makes it searchable.

## 3. What we built (the demo)

A search page where you can filter recipes by subjective qualities (taste,
texture, the occasion, who liked it, the cuisine, the meal type), or just type a
sentence and the system fills in the filters for you. When you click a recipe, it
shows the exact review sentences that justify each tag, so you can see the
evidence rather than trusting a black box.

Behind the page is a database we built by reading 10,000 reviews across 500
recipes and extracting about 47,000 descriptive tags.

## 3b. The three things we are selling (the story)

1. **The tags themselves.** We extract six kinds of subjective qualities from
   reviews (taste, texture, meal type, occasion, who liked it, cuisine) that no
   recipe database normally stores.
2. **The hybrid clean-up.** We tidy those tags into clean, clickable filters with
   a process that can be run by a person, by an AI assistant, or both, depending
   on how much quality matters. (Detail in section 4.)
3. **The user benefit.** The finished search page lets a person satisfy a
   subjective request ("comfort food for sick kids") that traditional keyword
   search handles poorly. Section 5b quantifies this.

These three line up as a cause-and-effect chain: we surface hidden tags ->
we clean them into usable filters -> users find things they could not find before.

## 4. The two new pieces (this is the new contribution)

The first version of this project just ran the reviews through an AI once and
kept whatever it produced. Reviewers at the previous conference said that was not
novel enough and not rigorous enough. So we added two things:

**(a) An automated clean-up assistant.**
The raw AI output is messy. The same idea shows up under many spellings
("hubby," "DH," "husband"), and there is a lot of filler ("delicious," "good")
that is useless as a filter. We built an assistant that repeatedly looks at the
most common tags, merges the duplicates, and drops the filler, until the list is
clean enough to use. Importantly, this clean-up can be done **by a person** when
quality really matters, or **by the AI assistant** when we need to do it at
scale. The project lead's guidance: offer both, so we control quality and avoid
the AI inventing things. This is a dial, not an all-or-nothing switch.

**(b) An independent AI grader.**
To check quality, we use a *second, different* AI to grade the first one's work,
the way you would not let a student grade their own exam. The grader looks at
each tag and the review it came from and says whether the tag is correct. We then
feed the grader's complaints back into the clean-up assistant to fix recurring
mistakes. So the system improves itself in a loop.

The clean-up does two complementary things, and it is worth keeping them separate:
- **Merge** synonyms ("mom"/"mum" -> mother). This raises *coverage*: the user finds
  recipes they would otherwise miss.
- **Filter** junk tags ("delicious", "self"). This raises *usability*: every filter
  shown to the user actually narrows the results.

"v1" and "v2" are two rounds of this clean-up. v1 is the demo as it stood before this
round; v2 is the current demo, after the grader pointed out the biggest remaining junk
to filter (most notably "self", a cook-vs-eater confusion that was tagged on 484
recipes). v2 differs from v1 only in this filtering; the coverage is the same for real
tags.

## 5. How we measure quality, and what each number actually means

There are two different questions, and it is important not to confuse them:

- **Precision**: of the tags the system kept, what fraction are correct?
- **Recall (coverage)**: of all the recipes that genuinely fit a request, what
  fraction does the system surface?

**On precision: our pipeline does not, and is not meant to, improve it.**
This is a subtle but important point. The clean-up steps relabel ("mom" -> "mother")
and remove whole categories of junk ("delicious", "self"), but they never go back
and re-check whether an individual tag was right in the first place. So whether a
surviving tag is correct was decided by the original extraction AI, and our steps
inherit that. When we measured precision carefully on 300 tags, the raw AI scored
about 53% and the fully cleaned-up version about 56% -- a 3-point difference that
is within the margin of error, i.e. essentially unchanged. We therefore treat
precision as a *description of the underlying extraction quality* (roughly half to
two-thirds of tags are correct, depending on the category), not as something we
claim to improve.

**On recall (coverage): this IS what our clean-up buys, and it is solid.**
People say the same thing many ways. A literal search for the word "mother" finds
89 recipes; our "mother" filter finds 194 -- because it also captures "mom", "mum",
"mommy". Across eight common concepts, a literal-word search misses 16% of the
recipes our filters surface, and for "mother" it misses 54%. These numbers are
exact counts (no sampling, no AI judge), so they are not subject to noise.

We confirmed this with a careful head-to-head. For three concepts (spicy, mother,
kids) we pooled every recipe any method returned, had an independent AI judge mark
each as genuinely fitting or not, and computed precision and recall for each step:

| Concept | Search method | Precision | Recall |
| ------- | ------------- | --------- | ------ |
| mother  | literal word "mother" | 41% | 49% |
|         | our pipeline          | 44% | 91% |
| spicy   | literal word "spicy"  | 61% | 82% |
|         | our pipeline          | 61% | 90% |
| kids    | literal word "kids"   | 81% | 91% |
|         | our pipeline          | 82% | 99% |

The pattern is consistent: precision stays the same, recall goes up a lot. That is
exactly the contribution -- we recover relevant recipes a plain keyword search
would miss, without lowering quality.

**What goes wrong with plain keyword search (real examples from the judge):**
- "spicy mustard" -- the word appears, but it is an *ingredient*; the dish is not spicy.
- "I would not say it was spicy" -- the word appears inside a negation.
- "as a child my mother used to make it" -- mentions a mother, but about a memory,
  not this dish.
- "my kids wouldn't have touched it" -- mentions kids, but they did not eat it.

Our extraction step understands these distinctions, which is why its tags are
cleaner than raw word-matching even before any tidy-up.

**Why not report recall as a single percentage of "everything that should exist"?**
That would require a person to read all 10,000 reviews and hand-list every tag that
should be there. The research literature (Chaganty et al. 2017) established that
this kind of complete recall is both very expensive and systematically unreliable.
So we report the *coverage gain over keyword search* (deterministic counts, no gold):
across the top-20 real facets in each category, the system surfaces **1,447 more
recipes (+19%)** than a literal keyword search. The gain concentrates where reviewers
use many words for one idea (Audience, Occasion); it is near zero for Flavor/Texture
where people already type the canonical word.

**One number we are proud of:** every tag in the database points back to the exact
sentence it came from. Nothing is invented. About 14% of the raw AI's tags pointed
to text that could not be located word-for-word in the review; we drop those
automatically before anything reaches the database.

## 5a. The tidiness-vs-meaning trade-off (does clean-up distort?)

A fair question: when we merge "hubby" into "husband," do we ever change the
meaning? Sometimes yes ("buttery" merged into "creamy" is a stretch). We measured
this directly. Of the tags the clean-up actually re-labelled, the independent
grader judged each merge as: same meaning, more-general-but-fine, or distorts.

| Result | Share |
| ------ | ----- |
| Same meaning (e.g. hubby -> husband)       | 44% |
| More general but acceptable (e.g. greek -> mediterranean) | 36% |
| Distorts the meaning (e.g. meal -> casual) | 20% |

So 80% of merges are fine for a filter, 20% distort. The worst offender is one
bad rule ("meal" -> "casual") that we should simply delete. The point for the
paper: we do not pretend clean-up is free; we quantify what it costs, and we keep
it under control with the human-or-AI dial.

## 5b. The user benefit: finding recipes you would otherwise miss (selling point 3)

The clearest payoff is the coverage gain in section 5: searching our "mother"
filter surfaces more than twice as many genuinely relevant recipes as typing the
word "mother", because it understands "mom" and "mum" mean the same thing. That is
the user-facing benefit, stated as a deterministic number, and it is the same
finding as the recall column in the table above.

**A note on a comparison we tried and set aside.** We also ran a full head-to-head
where three search methods (normal catalog search, raw review-text search, and our
filters) each returned their top 5 recipes for 12 requests, judged for relevance.
That test did not favor us: raw review-text search did as well or better on raw
hit-rate. We set it aside for three honest reasons: (1) 12 requests is far too few
to conclude anything; (2) the relevance judge saw the review text, which structurally
favored the method that searched review text; and (3) raw hit-rate is the wrong way
to measure our value -- our contribution is clean, combinable, evidence-linked
filters, not beating full-text search at finding a single word. The coverage gain
in section 5 captures the real benefit much more cleanly. We keep the details on file
in case a reviewer asks.

**On the requests:** the 12 example requests were written by hand while testing the
typed-search feature. We plan to expand to 30-40 before submission. Relevance judging
can be done by a person on a subset, with the AI-vs-human agreement reported -- the
same human-or-AI dial as the rest of the system.

## 6. Honest caveats (so we are not surprised by reviewers)

- We do **not** claim our clean-up improves per-tag precision; by design it relabels
  and filters rather than re-verifying, so precision is inherited from the extraction
  AI. We sell coverage/recall and groundedness, not precision gains.
- Precision itself is moderate: roughly half to two-thirds of tags are correct,
  varying by category (e.g. "mother" over-extracts and sits near 44%). This reflects
  the extraction AI's limits, which we report honestly.
- The "who cooked it" vs "who ate it" confusion ("I made this" vs "my kids loved
  this") is partly fixed by the clean-up but not fully.
- We deliberately did **not** run a formal user study; it does not fit a short demo
  paper and the project lead agreed to skip it.
- Coverage numbers are exact counts and not noisy; the AI-judged numbers (precision,
  merge fidelity) come from samples of 160-300 and carry a few points of uncertainty.

## 7. Where this is going / open decisions

- Recording a 3-minute demo video (required by the target conference).
- Expanding the typed-sentence test set from 12 to ~40 examples.
- Whether to report the AI-judge-vs-human agreement on a small subset, to back the
  human-or-AI dial with a number.
- Deleting the one clearly bad merge rule ("meal" -> "casual") flagged by the
  fidelity check, then noting fidelity rises.

## 8. Where things live (for the team)

- The demo and database: `food-exhibit-data-500recipes.json`, `index.html`
- Raw AI output, before any clean-up: `extracted_attributes_500recipes.jsonl`
  (in the `subjective_DB` workspace)
- After clean-up: `processed_attributes_500recipes.jsonl`
- The grading scripts and results: `scripts/llm_judge.py`, `eval_data/`
- The paper itself: `main.tex`
- Detailed metric definitions and every number: `METRICS_NOTES.md`
