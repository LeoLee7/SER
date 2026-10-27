# Finer-Grained Feature Extraction Prompt v1

**Version**: 1.0
**Date**: 2026-02-04
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
- Examples: Italian, Mexican, Asian, Southern, homestyle, French, fusion, Chinese

---

## CRITICAL EXTRACTION RULES

### Rule 1: Multi-Entity Extraction
For compound mentions, extract EACH entity separately:
- "husband and son loved it" → TWO separate features: [husband], [son]
- "kids and adults enjoyed" → TWO separate features: [kids], [adults]
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
- "husband loved it" → entity: "husband", polarity: "include" (default)

### Rule 4: Normalize Entities
Use clear, normalized entity names:
- "hubby" → "husband"
- "kiddos" → "kids"
- "Xmas" → "Christmas"
- "DH" (dear husband) → "husband"
- "mom" → "mother"

### Rule 5: Keep Negations in Attributes
- "not too sweet" → keep as "not too sweet"
- "not crispy enough" → keep as "not crispy"

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

---

Now extract features from the following review:
