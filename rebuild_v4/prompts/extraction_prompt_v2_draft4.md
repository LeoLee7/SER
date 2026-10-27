# Finer-Grained Feature Extraction Prompt v2

**Version**: 2.0
**Date**: 2026-10-24 (v1 dimensions and schema; rules rewritten from observed failures, see rebuild_v4/DESIGN.md)
**Purpose**: Extract subjective product features from food recipe reviews with multi-entity extraction, sentiment tracking, and polarity tracking.

---

You are extracting subjective product features from food recipe reviews.

Extract features according to these 6 independent dimensions:

### 1. taste_flavor
**Taste and flavor profile of the food**
- Examples: delicious, bland, sweet, salty, spicy, rich, well-seasoned, flavorful, tangy

### 2. texture_mouthfeel
**Physical feel and consistency in the mouth**
- Examples: crispy, tender, moist, dry, fluffy, creamy, chewy, crunchy, smooth

### 3. meal_type
**When to serve this dish (meal timing)**
- Examples: breakfast, lunch, dinner, snack, dessert, appetizer, side dish, brunch
- Extract ONLY explicit meal type mentions (not general occasions like "party")

### 4. occasion_holiday
**Events, holidays, or occasions to serve the dish**
- Examples: Christmas, Thanksgiving, birthday, party, potluck, weeknight, summer BBQ, game day
- Extract general occasions and specific events (not meal types like "dinner")

### 5. audience_enjoyment
**Who enjoyed eating the dish (NOT who cooked it)**
- Examples: kids, husband, family, guests, picky eaters, grandmother, friends
- IMPORTANT: Extract who ATE/ENJOYED, not who MADE it
- For compound mentions like "husband and son loved it", extract BOTH as separate entities

### 6. cuisine_type
**Cuisine style or cultural/regional origin**
- Examples: Italian, Mexican, Asian, Southern, French, Chinese, Cajun, Tex-Mex

---

## CRITICAL EXTRACTION RULES

### Rule 1: Multi-Entity Extraction
For compound mentions, extract EACH entity separately:
- "husband and son loved it" → TWO separate features: [husband], [son]
- "my mom and sister" → TWO separate features: [mother], [sister]

### Rule 2: Sentiment Tracking
Separate the entity from the sentiment:
- "husband loved it" → entity: "husband", sentiment: "positive"
- "husband disliked it" → entity: "husband", sentiment: "negative"
- "made for Thanksgiving" → entity: "Thanksgiving", sentiment: "neutral"

### Rule 3: Include/Exclude Polarity
Track whether something is FOR or NOT FOR a group:
- "perfect for vegetarians" → entity: "vegetarian", polarity: "include"
- "not for vegetarians" → entity: "vegetarian", polarity: "exclude"

### Rule 4: Normalize Entities to a Base Form
Use the plain base form of the word:
- "hubby", "DH" → "husband"; "kiddos" → "kids"; "mom" → "mother"; "Xmas" → "Christmas"
- "crispness", "crisp" → "crispy"; "fluffier" → "fluffy"; "thicker" → "thick"; "flavour" → "flavor"

### Rule 5: Keep Negations in Attributes
- "not too sweet" → keep as "not too sweet"
- "not crispy enough" → keep as "not crispy", sentiment: "negative"

### Rule 6: Not the Reviewer
Never extract the reviewer or a pronoun (I, me, myself, we, us, you, they, everyone) as audience_enjoyment. Extract a named person or group only.
- "I loved it" → nothing; "we all loved it" → nothing
- "my family loved it" → [family]; "my husband made it for me" → nothing (the husband cooked)
- "made it for my husband, he loved it" → [husband]

### Rule 7: Only This Dish, As It Was Eaten
Every feature must describe THIS recipe as the reviewer made or ate it.
- Another dish served alongside: "served it with Mexican rice", "served with steamed broccoli" → nothing
- Another recipe or product: "I used it with the Delicious Chicken Pot Pie recipe", "better than the store bought pie" → nothing
- Changes, fixes, and plans: "the sauce needed thickening", "next time I will add more garlic", "add cayenne for more kick" → nothing
- Memories and gifts: "as a child my mother used to make it", "my mother-in-law gave me the recipe" → nothing
- occasion_holiday and meal_type only when this dish was served then or as that: "made it for Christmas dinner" → [Christmas], [dinner]; "made it a month before Thanksgiving" → nothing; "made it as a side dish" → [side dish]

### Rule 8: Cuisine Only When Said of This Dish
Extract cuisine_type only when the review says this dish is, tastes like, or was used as a named cuisine or region.
- "tastes like real Thai food" → [Thai]; "my favorite Chinese chicken dish" → [Chinese]; "authentic Mexican flavor" → [Mexican]; "we used it as taco filling" → [Mexican]
- A cuisine word naming an ingredient or place: "Mexican cheese", "Italian seasoning", "our favorite Mexican restaurant" → nothing
- A restaurant or brand is not a cuisine: "just like Panera", "Pizza Hut crust" → nothing
- Do not infer cuisine from ingredients or dish type: a pie crust, a roast turkey → nothing

### Rule 9: The Entity Is the Attribute Word
`entity` is the attribute itself, one to three words, an adjective or noun from the review.
- No verbs, comparisons, or the food's name: "love what it tastes like" → nothing; "cornbread texture" → nothing; "the sauce" → nothing
- Generic praise is not a flavor, never output it: delicious, good, great, tasty, yummy, amazing, wonderful, perfect, best, excellent, incredible, just right → nothing
- An ingredient is not a flavor: "beans", "butter", "salt", "spicy brown mustard" → nothing; a flavor word stays: "garlicky", "cheesy", "smoky" → [garlicky], [cheesy], [smoky]
- texture_mouthfeel is physical feel only: "came out perfectly crispy" → [crispy]; "easy", "perfectly", "nicely" → nothing

### Rule 10: Sentiment Belongs to the Feature
Sentiment says whether that feature was a good experience, not the mood of the whole review.
- "served it at Christmas, but it wasn't crispy" → [Christmas] neutral, [not crispy] negative
- "the kids hated it" → [kids] negative

### Rule 11: Exact Evidence
`source_text` is copied character for character from the review, the shortest clause that shows the feature.

---

## OUTPUT FORMAT

Return a JSON array of extracted features. Each feature should have:
- `dimension`: one of the 6 dimensions above
- `entity`: the normalized entity/attribute
- `sentiment`: "positive", "negative", or "neutral"
- `polarity`: "include" (default) or "exclude"
- `source_text`: the exact quote from the review where this was extracted

```json
[
  {
    "dimension": "audience_enjoyment",
    "entity": "husband",
    "sentiment": "positive",
    "polarity": "include",
    "source_text": "My husband loved this"
  }
]
```

---

## EXAMPLE

**Review**: "Made this for Thanksgiving and everyone loved it! My grandmother said it reminded her of her childhood. The kids asked for seconds. The flavors were absolutely delicious and the chicken was so tender."

**Output**:
```json
[
  {
    "dimension": "occasion_holiday",
    "entity": "Thanksgiving",
    "sentiment": "neutral",
    "polarity": "include",
    "source_text": "Made this for Thanksgiving"
  },
  {
    "dimension": "audience_enjoyment",
    "entity": "everyone",
    "sentiment": "positive",
    "polarity": "include",
    "source_text": "everyone loved it"
  },
  {
    "dimension": "audience_enjoyment",
    "entity": "grandmother",
    "sentiment": "positive",
    "polarity": "include",
    "source_text": "My grandmother said it reminded her of her childhood"
  },
  {
    "dimension": "audience_enjoyment",
    "entity": "kids",
    "sentiment": "positive",
    "polarity": "include",
    "source_text": "The kids asked for seconds"
  },
  {
    "dimension": "taste_flavor",
    "entity": "delicious",
    "sentiment": "positive",
    "polarity": "include",
    "source_text": "absolutely delicious"
  },
  {
    "dimension": "texture_mouthfeel",
    "entity": "tender",
    "sentiment": "positive",
    "polarity": "include",
    "source_text": "the chicken was so tender"
  }
]
```


**Review**: "I'm not a fan of spicy food but my DH loved it. I served it with Mexican rice for a weeknight dinner. The chicken came out crispy, and next time I'll add more cumin. Way better than our local Mexican restaurant!"

**Output**:
```json
[
  {"dimension": "audience_enjoyment", "entity": "husband", "sentiment": "positive", "polarity": "include", "source_text": "my DH loved it"},
  {"dimension": "occasion_holiday", "entity": "weeknight", "sentiment": "neutral", "polarity": "include", "source_text": "for a weeknight dinner"},
  {"dimension": "meal_type", "entity": "dinner", "sentiment": "neutral", "polarity": "include", "source_text": "for a weeknight dinner"},
  {"dimension": "texture_mouthfeel", "entity": "crispy", "sentiment": "positive", "polarity": "include", "source_text": "The chicken came out crispy"}
]
```
Not extracted: "I'm not a fan" (the reviewer), "Mexican rice" (a side dish), "more cumin" (a plan), "Mexican restaurant" (a place).

---

Now extract features from the following review:
