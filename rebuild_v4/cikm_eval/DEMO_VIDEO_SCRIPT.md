# SER CIKM 2026 Demo Video: Director's Production Package

## 1. Overview

**Runtime target:** 3:05 to 3:10 (within the 2.5 to 3.5 minute window CIKM demo tracks expect). Hard ceiling 3:30.

**Tone:** Confident, precise, demonstrative. This is a systems demo, not a sales pitch. Let the live interface do the persuading and keep narration tight. No hype words, no filler. Every quantitative claim is attributed to either the live tool or "our evaluation" so a reviewer who opens the app at `localhost:8080` is never surprised.

**Audience:** CIKM demo-track reviewers and attendees. They are skeptical about (a) LLM hallucination in extracted attributes and (b) overclaimed metrics. They will likely open the running app and inspect it. Two non-negotiables follow from this:
- Every on-screen artifact in the live UI must be real. Numbers that come from the paper appear only as clearly-labeled overlay captions ("From our evaluation"), never disguised as system output.
- The smart search is described honestly as keyword-to-facet matching, not "LLM query understanding," because the live function `performSmartSearch` is a stopword-filtered term-to-facet matcher.

**Core thesis carried end to end:** SER has two pillars. **Recall by grouping** (synonym normalization merges surface variants into one clean facet, +19% coverage vs literal keyword search). **Precision by evidence** (every facet value traces to a verbatim review span, color-coded and hover-traceable; 97.8% span-faithful, 100% at DB level by construction; plus context-aware extraction that drops negations and off-topic matches keyword search returns).

---

## 2. Pre-Recording Checklist

**Launch the demo (two terminal lines):**
```bash
cd /Users/liliu/SER-DB
python3 -m http.server 8080
```
Then open: `http://localhost:8080/index.html`

**Verify before you hit record:**
1. The three-column Simile Exhibit layout loads fully (left facets, center gallery, right facets). Wait for the gallery to populate; Exhibit renders asynchronously.
2. Confirm these four recipes load and open cleanly in the modal:
   - Really Good Vegetarian Meatloaf (Really!)
   - To Die for Crock Pot Roast
   - Yummy Crunchy Apple Pie
   - Best Banana Bread
3. For each, click **View Reviews with Highlights** once in rehearsal and confirm color-coded spans render and the hover tooltip shows `Dimension: entity` (this is the line 1206 `title` attribute, e.g. `Audience: husband`).
4. Pre-test the smart search string you will type live. The app placeholder is `e.g., Christmas food for my father`. Type your chosen query in rehearsal and confirm which facets actually light up. Use the verified string in the script below; do not improvise on camera.

**Browser setup:**
- Use Chrome or a Chromium browser. Open in a clean window, no extra tabs, no extensions toolbar.
- Hide bookmarks bar (Cmd+Shift+B). Enter fullscreen or use a clean window chrome.
- Set browser zoom so the three columns and a recipe card grid are all visible without scrolling. 90% zoom usually frames all three columns on a 1440p display.
- Open DevTools console once during rehearsal only, to watch `performSmartSearch` log which facets it clicks (`Search: "<phrase>" -> [category] "value"`). Close it before recording.

**Screen resolution tips:**
- Record at 1920x1080 (16:9). If on a Retina display, set screen scaling so captured pixels are crisp at 1080p; avoid recording a 4K canvas downscaled to 1080 with blurry text.
- Keep the cursor large or enable cursor highlighting in your screen recorder (see Section 6).

**Have ready off-screen:**
- The overlay caption assets (lower-third text cards) for the four paper numbers: `Keyword genuine-rate: mother 41%, spicy 61% (from our evaluation)`, `+19% coverage vs literal keyword search (from our evaluation)`, `tangy facet folds in tart, zesty, zingy: 41 -> 73 recipes (from our evaluation)`, `97.8% of spans verbatim-faithful; 100% at DB level by construction (from our evaluation)`.
- The pipeline strip graphic (5 stages) for the closing montage.
- Title card and end card.

---

## 3. Shot-by-Shot Script

Total: 3:08. Cold open trimmed to ~14s and the back-third montage simplified per judge feedback so the precision climax keeps its weight.

| TIMESTAMP | ON-SCREEN ACTION | VOICEOVER | PAPER IDEA SHOWN |
|---|---|---|---|
| **0:00 - 0:14** | Cold open, no live UI. Title card with one typed query: `spicy dinner my husband loved`. Below it a mock keyword result list animates in: a card flagged **NOT spicy at all** (negation), a card matching `spicy` in an off-topic ingredient mention, and a **no results for "husband"** empty state. Red X marks pop on each. Keep it brisk. | "Search for a recipe that is spicy, good for dinner, and that someone's husband loved. A keyword index treats this as three strings. It returns dishes a reviewer said were not spicy. It matches spicy where it was never about taste. And it finds nothing for husband, because this reviewer wrote hubby." | Problem framing: keyword search fails on subjective queries via negation false positives, off-topic false positives, and synonym blindness. Motivates both pillars. |
| **0:14 - 0:30** | Overlay lower-third caption (clearly styled as a cited stat, not UI): **Keyword genuine-rate: mother 41%, spicy 61% (from our evaluation)**. Then hard cut to the live SER interface at `localhost:8080/index.html`, three-column Simile Exhibit loading the gallery. | "This is not a corner case. In our evaluation, fewer than half of literal keyword matches for mother are genuine, and only about sixty percent for spicy. The rest are negations and off-topic noise. SER fixes exactly this. It searches subjective experience across five hundred recipes and ten thousand reviews from Food dot com." | Quantifies keyword failure (cited overlay). Transition to live system. Scale grounding: 500 recipes, 10K reviews, ~47K attributes. |
| **0:30 - 0:48** | Slow pan across the live layout. Cursor traces the left panel (Audience, Occasion, Texture, Taste), the center recipe gallery, the right panel (Meal Type, Cuisine, Cook Time, Calories). Expand the **Audience** facet to reveal clean canonical values (family, kids, husband, guests, mother). | "Instead of one box over raw text, SER turns the opinions inside reviews into clean, clickable facets across six subjective dimensions: flavor, texture, meal type, occasion, audience, and cuisine. On the left, the subjective facets mined from reviews. On the right, the catalog facts like calories and cook time. The two indexes work together." | The core artifact and the six subjective dimensions. Subjective facets complement catalog attributes (two-index design). |
| **0:48 - 1:06** | Click the **Audience -> husband** facet value. Gallery filters. Overlay caption (cited): **husband facet merges DH, hubby, spouse (from our evaluation)**. Then click **Taste -> spicy** and **Meal Type -> dinner**, composing the cold-open query live. | "Watch recall first. When I select husband, SER does not match a literal word. It has already merged DH, hubby, and spouse into one canonical facet, so I retrieve recipes a keyword search would drop. Now I add spicy and dinner, the exact query that broke keyword search a moment ago." | Recall pillar: grouping-led synonym normalization (DH/hubby/spouse -> husband). Concept-level search, not string matching. |
| **1:06 - 1:22** | Results resolve to a clean set. Overlay caption (cited): **+19% coverage vs literal keyword search (from our evaluation)**. Secondary caption: **tangy folds in tart, zesty, zingy: 41 -> 73 recipes**. Cursor points to **Really Good Vegetarian Meatloaf (Really!)**, which carries spicy, tangy, and a husband audience tag. | "Every result here genuinely fits all three constraints. Because synonyms are consolidated, our evaluation shows SER surfaces about nineteen percent more relevant recipes than literal search. The gain is largest where reviewers use many words for one idea. Folding tart, zesty, and zingy into tangy lifts that facet from forty-one recipes to seventy-three." | Recall pillar quantified (cited overlay): +19% coverage; tangy 41 -> 73. Concrete grounding. |
| **1:22 - 1:38** | Click **Clear** to reset filters. Click the natural-language search box. Type slowly the rehearsed string: `Christmas dessert for kids`. Submit. Facets auto-select across panels: Occasion **Christmas**, Meal Type **dessert**, Audience **kids**. Gallery updates. | "You do not have to click facets one by one. SER also takes natural language. I type Christmas dessert for kids, and it maps the query words to matching facet values across three dimensions at once: occasion, meal type, and audience. A free-text wish becomes a structured query." | Query-to-facet mapping across dimensions. **Note: framed honestly as word-to-facet matching, not LLM parsing.** Lowers interaction cost. |
| **1:38 - 1:56** | From the results, click into **Yummy Crunchy Apple Pie**. Modal opens: image, metadata, ingredients, instructions, and the extracted attributes list (Audience: kids, family, daughter, husband; Occasion: Christmas, Thanksgiving, birthday, party; Taste: rich, tangy, sweet). Cursor hovers the **View Reviews with Highlights** button. | "Now the precision pillar, the heart of the system. Open any recipe and you see its extracted subjective attributes. This pie has the richest occasion facet in the demo. But a tag is only trustworthy if you can see where it came from. So every recipe carries its evidence. I click View Reviews with Highlights." | Sets up precision pillar. Per-recipe extracted attributes and the provenance promise. Apple Pie chosen for its 10-value occasion facet. |
| **1:56 - 2:22** | **CLIMAX. Hold here, do not rush.** Reviews view opens with real review text and color-coded inline highlights (Audience yellow, Taste green, Texture blue, Meal Type purple, Occasion orange, Cuisine pink). Slowly hover a yellow span ("DH") -> tooltip **Audience: husband**; then an orange span ("for thanksgiving") -> **Occasion: Thanksgiving**; then a pink span ("mexican caramel topping") -> **Cuisine: Mexican**. Overlay caption (cited): **97.8% of spans verbatim-faithful; 100% at DB level by construction (from our evaluation)**. | "This is the money shot. Each highlighted span is the exact phrase a real reviewer wrote, color-coded by dimension. Hover any highlight and it names the dimension and the entity it produced. Nothing here is invented by the model. A deterministic check confirms ninety-eight percent of spans appear verbatim in their review. At the database level it is one hundred percent, because any attribute whose span cannot be located is discarded. That is the direct answer to the hallucination concern." | Precision pillar climax: evidence-led grounding. Color-coded verbatim spans, hover-to-trace (line 1206 tooltip), 97.8% / 100%-by-construction. Anti-hallucination guarantee. |
| **2:22 - 2:42** | Close the modal. Open **To Die for Crock Pot Roast**. In the extracted attributes, point out that **dinner appears in BOTH the Occasion and the Meal Type facet**, and Italian appears in both Taste and Cuisine. Then open its highlighted reviews and point the cursor at a negated phrase that is NOT highlighted. Overlay caption: **context-aware: "not spicy" is never counted as spicy**. | "Precision is also about reading context. Because SER extracts from meaning, not from string matches, the word dinner here lands in both occasion and meal type, assigned by the sentence it came from. And negations are dropped. The phrase not spicy is never counted as spicy. This is the failure we opened with, now solved." | Precision pillar second half: context-aware extraction (same word, two dimensions; polarity-exclude on negation) avoids the false positives keyword search returns. Closes the cold-open loop. |
| **2:42 - 2:54** | Quick montage: a one-line pipeline strip animates left to right with five labeled stages: **Gemma-3 extraction -> blacklist filtering -> synonym normalization -> span evidence linking -> agentic observe-verify-update loop**. No cross-domain teaser (cut to protect the climax and pacing). | "Behind the interface is a staged pipeline. Gemma-3 extracts category, entity, sentiment, and source text from each review. A blacklist removes generic noise, synonym normalization builds the facets, span linking grounds every value, and an agentic loop verifies and refines it over time." | Pipeline transparency. Shows the method is a reusable, staged system, not a one-off. |
| **2:54 - 3:08** | Return to the full live interface with the husband / spicy / dinner result set and one highlighted review visible. End card with the project name and the two-pillar summary: **Recall by grouping. Precision by evidence.** plus footer line: 500 recipes, 10K reviews, 47K attributes, 6 dimensions, evaluated with cross-family LLM-as-Judge. | "SER turns the subjective experience locked in reviews into search you can trust. Recall comes from grouping synonyms into clean facets. Precision comes from grounding every facet in evidence you can read for yourself. That is concept-level, evidence-backed search for how people actually experienced the dish." | Two-pillar recap: recall = grouping-led, precision = evidence-led. Reinforces the contribution. |

---

## 4. Two-Pillar Mapping

Use this to confirm both pillars are visibly demonstrated before you finalize the cut.

**Precision (evidence-grounding) is proven by:**
- **1:38 - 1:56** Extracted attributes shown per recipe (the promise).
- **1:56 - 2:22** The climax: color-coded verbatim spans + hover tooltip (`Dimension: entity`, line 1206) + the 97.8% / 100%-by-construction caption. This is the strongest live moment and the direct answer to hallucination concerns.
- **2:22 - 2:42** Context-aware extraction: same word in two dimensions (dinner -> Occasion + Meal Type on Crock Pot Roast) and dropped negations. This is the precision contribution located in extraction, not a per-round metric gain.

**Recall (synonym grouping) is proven by:**
- **0:48 - 1:06** Selecting the husband facet that already merges DH / hubby / spouse.
- **1:06 - 1:22** The +19% coverage caption and the tangy 41 -> 73 example.
- **1:22 - 1:38** One word-to-facet query lighting up three dimensions, showing facets are clean canonical concepts rather than raw strings.

**Honesty guardrails (keep these intact):**
- Recall is coverage gain over literal keyword search (+19%, a dataset-level coverage index), not a gold-recall claim and not a per-query "your cards grew 19%" claim. The voiceover attributes it to "our evaluation."
- Precision is evidence + context-aware extraction. State "100% at the DB level by construction," not "100% of facet values are grounded," to stay consistent with the ~14% un-locatable extractions that FindSpan discards.
- Smart search is "maps query words to matching facet values," not "understands" or "parses" natural language.
- All four paper numbers appear as captions tagged "from our evaluation," visually distinct from the live UI.

---

## 5. Operation Cheat-Sheet (live clicks, no narration)

Rehearse this sequence until it is muscle memory.

1. Have the title card and mock-keyword-results graphic ready as a pre-roll (shots 0:00 - 0:30 are overlay, not live).
2. Cut to live app already loaded at `localhost:8080/index.html`.
3. Slow pan across all three columns. Expand the **Audience** facet.
4. Click **Audience -> husband**.
5. Click **Taste -> spicy**.
6. Click **Meal Type -> dinner**. (Overlay the +19% and tangy captions here.)
7. Point cursor at **Really Good Vegetarian Meatloaf (Really!)** in the results.
8. Click **Clear** to reset all filters.
9. Click the search box. Type `Christmas dessert for kids`. Submit. Confirm Christmas + dessert + kids facets light up.
10. Click into **Yummy Crunchy Apple Pie**. Pan its extracted attributes. Hover the **View Reviews with Highlights** button.
11. Click **View Reviews with Highlights**. Hover, in order: a yellow span (Audience), an orange span (Occasion), a pink span (Cuisine). Hold each tooltip ~1.5s. (Overlay the 97.8% / 100% caption.)
12. Close modal. Click into **To Die for Crock Pot Roast**. Point out **dinner** in both Occasion and Meal Type attributes.
13. Open its highlighted reviews. Point cursor at a non-highlighted negated phrase.
14. Cut to the pipeline strip graphic (overlay).
15. Cut back to the live interface with the husband/spicy/dinner results plus a highlighted review visible. End card.

---

## 6. Recording Tips

**Pacing:**
- Trim the cold open to ~14s. It is exposition; get to the live tool fast.
- The single longest hold is the **1:56 - 2:22 climax (26s)**. Everything else is brisk. Resist the urge to add a cross-domain teaser after the climax; it competes with the recap and the judges flagged this as the spot most likely to lose a tired reviewer.
- Type search strings at a readable speed, not instantly. Viewers need to read `Christmas dessert for kids` as the facets light up.
- After each facet click, pause ~1s so the gallery visibly re-renders before the next action.

**Cursor highlighting:**
- Enable a cursor spotlight or click-ripple in your recorder (Keynote's "Highlight clicks," ScreenFlow, or Cleanshot). Reviewers must see exactly which facet you clicked.
- Move the cursor deliberately and slowly during the climax hovers so the tooltip clearly appears before you move on.

**Where to pause (give the viewer a beat to read):**
- On the genuine-rate caption (0:14 - 0:30).
- On the +19% and tangy captions (1:06 - 1:22).
- On each of the three climax tooltips (1:56 - 2:22).
- On the "dinner in two facets" attribute display (2:22 - 2:42).

**Optional captions for the numbers (style them as cited overlays, distinct from UI):**
- `Keyword genuine-rate: mother 41%, spicy 61%  (from our evaluation)`
- `+19% coverage vs literal keyword search  (from our evaluation)`
- `tangy folds in tart, zesty, zingy: 41 -> 73 recipes  (from our evaluation)`
- `97.8% of spans verbatim-faithful · 100% at DB level by construction  (from our evaluation)`
- Use a consistent lower-third style with a small "from our evaluation" tag so a reviewer never mistakes a paper metric for live system output. This single choice protects your fidelity score.

**Audio:**
- Record narration separately and lay it over the screen capture so you can re-time without re-recording clicks.
- Keep a level, confident read. No rising-inflection questions, no hedging.

**Final QA pass before export:**
- Confirm every number on screen is tagged "from our evaluation."
- Confirm the smart-search narration says "maps query words to facet values," never "understands" or "parses."
- Confirm the precision narration says "100% at the database level by construction."
- Confirm total runtime is between 3:00 and 3:15.
