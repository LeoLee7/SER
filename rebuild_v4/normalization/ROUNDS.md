# Normalization loop (observe-act-apply), v4

Agent: Claude, reading the frequency-sorted distributions in `observe_roundN.md` by hand (2026-10-25).
Input: `data/verified_v4.jsonl` (15,370 items). Maps: `data/synonyms_v4.json`, `data/blacklist_v4.json`.
Stopping rule (feature-normalization skill): top-30 values cover >= 80% of mentions and a round gains < 2%.
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

## Aggregation threshold
Minimum distinct supporting reviews per recipe: taste, texture, audience = 2; meal type, occasion, cuisine = 1. A single threshold failed both ways: at 1, husband covers 88% of recipes; at 2, Christmas falls from 17% to 5% and occasion queries return almost nothing. Sparse categories are mentioned rarely and explicitly, so one mention carries information; dense categories need agreement. Support counts are stored per value (`*_support` fields).
