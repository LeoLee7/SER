# Annotation rubric: recipe review facet values

Each tuple says: this review gives the recipe the value `value` in facet `category`, with `evidence` quoted from the review. The value will become a clickable facet in a recipe search engine (e.g. Audience = kids, Texture = crispy). Judge whether a searcher who clicks that facet value would be right to get this recipe, based on this review.

## Categories

- taste_flavor: a specific taste or flavor of the dish (sweet, tangy, spicy, garlicky, smoky, mild, rich, not too sweet).
- texture_mouthfeel: physical feel in the mouth (tender, crispy, moist, creamy, chewy, fluffy).
- meal_type: the role the dish played (breakfast, dinner, dessert, side dish, appetizer, snack).
- occasion_holiday: an event or time the dish was served for (Christmas, birthday, potluck, weeknight, game day).
- audience_enjoyment: a specific person or group who ate and liked it (husband, kids, guests, picky eaters).
- cuisine_type: the cuisine of this dish, as the reviewer describes it (Mexican, Italian, Chinese).

## Verdict

`correct` only if all hold: the value is a real attribute of THIS recipe as made or eaten, it belongs to the category, the evidence supports it, and it is usable as a facet value. Otherwise `wrong` with one code:

| code | meaning | example |
|---|---|---|
| generic_praise | quality word, not a specific attribute | delicious, good, great, perfect, wonderful |
| not_this_dish | about another dish, side, restaurant, product, or recipe name | "served with Mexican rice" -> Mexican |
| plan_or_change | a substitution, fix, or future plan | "needed thickening", "next time more garlic" |
| memory_or_gift | a memory or a gift, not this dish eaten | "my mother used to make it" -> mother |
| reviewer_or_vague_group | the reviewer, a pronoun, or an unspecific group | I, we, me, self, everyone, they |
| cook_not_eater | the person cooked it, not ate it | "my husband made it" -> husband |
| ingredient_not_attribute | an ingredient as a flavor, or a cuisine word modifying an ingredient | beans, butter; "Italian seasoning" -> Italian |
| negated_or_disliked | the review denies or dislikes it | "not spicy at all" -> spicy; "kids hated it" -> kids |
| occasion_not_served | occasion mentioned but the dish was not served for it | "a month before Thanksgiving" |
| wrong_category | real attribute, wrong category | easy -> texture |
| unsupported | evidence does not say this | |
| unusable_phrase | not a facet value: a sentence, comparison, or long phrase | "better than Panda Express" |

## Missed attributes

For each review, also list attributes the review clearly states that should be a facet value in one of the six categories and that NO tuple captures (any tuple with the same meaning counts as captured). Be conservative: only clear, facet-worthy attributes of this dish.

## Output

Write strict JSON to the output path:

```json
{"judgments": [{"id": "r000_t00", "verdict": "correct", "code": null, "note": ""}],
 "missed": [{"review_id": "r000", "category": "texture_mouthfeel", "value": "crispy", "evidence": "nice and crispy"}]}
```
Every tuple id in the packet must appear exactly once in `judgments`. `note` is optional, one short phrase.
