# Normalization loop (observe-act-apply), v4

Agent: Claude, reading the frequency-sorted distributions in `observe_roundN.md` by hand (2026-10-25).
Input: `data/verified_v4.jsonl` (15,370 items). Maps: `data/synonyms_v4.json`, `data/blacklist_v4.json`.
Stopping rule (feature-normalization skill): top-30 values cover >= 80% of mentions, or a round gains no more than 2 points.
Policy: merge surface variants and clear synonyms only; keep the six v1 categories; follow the paper's examples (tart/zesty -> tangy, hubby/DH -> husband, greek -> Mediterranean, not too spicy -> mild); blacklist values that are not an attribute of that category.

| Category | round 0 values / top-30 | round 1 | round 2 |
|---|---|---|---|
| taste_flavor | 530 / 62.1% | 464 / 75.9% | 428 / 77.9% |
| texture_mouthfeel | 351 / 85.1% | 293 / 89.9% | (no change) |
| meal_type | 43 / 99.1% | 9 / 100% | |
| occasion_holiday | 218 / 75.8% | 163 / 85.1% | |
| audience_enjoyment | 317 / 86.5% | 235 / 93.3% | |
| cuisine_type | 45 / 93.4% | 23 / 100% | |

## Round 1 (all categories)
- Taste: sweetness/sweeter/sugary -> sweet; lightly/slightly/less sweet, not overly sweet -> not too sweet; heat/kick/hot -> spicy; not too spicy/not spicy -> mild; tart/zesty/zing/zip/tang -> tangy; garlicky -> garlic (kept as canonical so the paper's Fig 1b and `test_paper_queries.py` stay valid); chocolatey spellings -> chocolate; depth/deep flavor -> complex; robust/intense/strong -> bold. Blacklist: filling, juicy, smooth, creamy (texture words), warm, authentic.
- Texture: crisp -> crispy (CIKM R4 crispy/crisp/crispness); crunch -> crunchy; crust/nice crust -> crusty; fork tender -> tender; fell apart/falling apart -> falls apart; flakey -> flaky; not dry -> moist; held together/held its shape -> holds together. Blacklist: appearance or temperature (golden brown, browned, glossy, cold, warm, frozen, tall) and non-texture (rich, hearty, bite, body, set).
- Meal type: supper -> dinner; entree/main course -> main dish; starter -> appetizer. Blacklist dish names (sandwich, salad, tacos, muffins, ...), which name a food, not a role.
- Occasion: canonical capitalization for holidays; birthday party -> birthday; cookout/barbecue -> bbq; football game/tailgating/game night -> game day; get-together/family reunion -> gathering; office party/work function -> work party; church function/supper/picnic -> church event; christmas eve -> Christmas.
- Audience: children/kid/N year old (4+) -> kids; 1 to 3 year old/baby -> toddler; picky eaters/picky kid -> picky eater; spouse/significant other -> partner; dad -> father; co-workers/colleagues/office -> coworkers; dinner guests/company/crowd -> guests; grandson/granddaughter -> grandkids. Blacklist pets and personal names (dog, cat, dugan, mariners).
- Cuisine: tex-mex/baja -> Mexican; sicilian/tuscan -> Italian; greek -> Mediterranean; teriyaki -> Japanese; oriental -> Asian; new orleans -> Cajun. Blacklist dish or sauce names (alfredo, caesar, buffalo, bbq, curry).

## Round 2 (taste only)
herby/herb -> herbs; strong/intense/full flavor -> bold; dark/rich chocolate, brownie -> chocolate; twang -> tangy; piquant -> spicy; no heat/subtle heat -> mild; aromatic -> fragrant. Blacklist: fudgy, saucy, homemade, plain, neutral, clean.
Gain 2.0%. Stopped. Taste stays below 80% because its tail is distinct flavor notes (ginger, almond, nutmeg, dill, molasses); merging them would distort meaning, the failure the CIKM merge-fidelity check found in 20% of merges.

## Post-loop fixes from the demo regression
- Texture blacklist: not crispy, not crunchy, not too crisp (negated values make no facet).
- Canonical crisp-tender (v3 name) instead of tender-crisp.

## Round 3 (2026-10-25, texture and audience tail, after the threshold change)
Lowering the texture and audience thresholds to 1 made their tails into facet values, so the tail was read once more. Texture: crispness, crisp crust, slightly crisp -> crispy; not overly dry, semi-moist -> moist; fudgey -> fudgy; tenderness -> tender; easy to spread -> spreadable. Blacklist: easy to cut/roll/slice/stretch, freezes well, right consistency, nice texture, sheen, shiny, fried, breaded, and other non-texture tail values. Audience: dads -> father; co-worker, work buddies -> coworkers; families -> family; little boy, eight year old -> kids; 13 year old, 16 yo -> teenagers. Blacklist pets, names, customers.

## Aggregation threshold
Final (deployed, tag v4-deployed-2026-10-25): minimum distinct supporting reviews per recipe, flavor = 2, every other category = 1; a value must apply to at least 2 recipes.
History: first set to taste, texture, audience = 2 and the rest = 1, because at 1 everywhere husband covers 88% of recipes and at 2 everywhere Christmas falls from 17% to 5%. The recipe-level blind eval then showed that pairs cut by the threshold were still correct 85% of the time for audience (17/20) and 75% for texture (15/20), but only 55% for flavor (11/20), so Li chose to lower texture and audience to 1 (2026-10-25). Support counts are stored per value (`*_support` fields).
