# Rubric: is this recipe a correct result for this facet?

A recipe search engine lets users click facet values built from reviews, such as Audience = kids or Flavor = tangy. Each item gives a facet (category and value), a recipe name, and the review sentences from that recipe's reviews that mention the facet word or were linked to it. Decide whether a user who clicks the facet is right to get this recipe, judging only from these sentences.

`correct` if at least one sentence says this recipe, as someone made or ate it, has that property:
- taste_flavor / texture_mouthfeel: the dish tasted or felt that way ("nice tangy sauce", "a little zesty").
- meal_type: it was served as that meal or role ("we had it for dinner", "great side dish").
- occasion_holiday: it was served for that event ("made it for Christmas").
- audience_enjoyment: that person or group ate and liked it ("my kids devoured it").
- cuisine_type: the reviewer describes this dish as that cuisine or uses it as such ("authentic Mexican flavor", "great taco filling").

`wrong` if no sentence does, for example: negated ("not spicy at all"), an ingredient or product ("Mexican cheese", "crispy fried onions"), another dish or place ("served with Mexican rice", "my favorite Mexican restaurant"), a plan or change ("next time I'll make it spicier"), a memory, the cook rather than the eater, a hypothetical ("if your kids are picky"), a dislike ("the kids hated it").

Synonyms count: "zesty" supports tangy, "my DH" supports husband, "the kiddos" supports kids.

Output strict JSON to the given path: `{"judgments": [{"id": "p0000", "verdict": "correct" | "wrong", "note": "<=8 words"}]}`. Every id in the packet exactly once.
