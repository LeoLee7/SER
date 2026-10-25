"""Build the v4 exhibit JSON from the v3 exhibit (catalog fields kept) and verified v4 extractions.

Review-derived fields are recomputed with the v4 synonym map and blacklist. A recipe carries a
value when at least min_support[category] distinct reviews assert it (DESIGN.md, F11). Every review keeps
all its normalized attributes with spans, so evidence highlighting still works.
Reviews are matched by text (the v3 exhibit holds 9,306 of the 10,000 reviews, in another order),
spans are relocated on the displayed text, and support counts only displayed reviews.

    python3 rebuild_v4/scripts/build_exhibit.py [--min-support taste_flavor=2,...]
"""
import argparse
import html
import re
import json
from collections import Counter, defaultdict
from pathlib import Path

from observe import DIMS, canon, load_maps

ROOT = Path(__file__).resolve().parent.parent
V3 = Path("/Users/liliu/SER-DB/food-exhibit-data-500recipes.json")
FIELD = {"taste_flavor": "taste_attributes", "texture_mouthfeel": "texture_attributes",
         "meal_type": "meal_type_attributes", "occasion_holiday": "occasion_attributes",
         "audience_enjoyment": "audience_attributes", "cuisine_type": "type_attributes"}


def norm(text):
    return re.sub(r"\s+", " ", html.unescape(html.unescape(text))).strip()


CATEGORY_LABEL = {"taste_flavor": "Taste-Flavor", "texture_mouthfeel": "Texture-Mouthfeel",
                  "meal_type": "Meal-Type", "occasion_holiday": "Occasion-Holiday",
                  "audience_enjoyment": "Audience-Enjoyment", "cuisine_type": "Cuisine-Type"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-support", default="taste_flavor=2,texture_mouthfeel=1,audience_enjoyment=1,meal_type=1,occasion_holiday=1,cuisine_type=1",
                    help="per-category minimum number of distinct reviews")
    ap.add_argument("--min-recipes", type=int, default=2, help="a facet value must be carried by this many recipes")
    ap.add_argument("--src", default=str(ROOT / "data" / "verified_v4.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data" / "food-exhibit-data-500recipes.v4.json"))
    args = ap.parse_args()
    inv, bl = load_maps()
    min_support = {k: int(v) for k, v in (p.split("=") for p in args.min_support.split(","))}

    by_text = {}
    for line in open(args.src):
        r = json.loads(line)
        by_text[(str(r["recipe_id"]), norm(r["review_text"]))] = r["attributes"]

    data = json.load(open(V3))
    kept, unmatched, relocated_fail = Counter(), 0, 0
    for item in data["items"]:
        rid = str(item["id"])
        support = defaultdict(Counter)  # dim -> value -> #reviews shown on this recipe
        reviews = item["reviews"] if isinstance(item["reviews"], list) else eval(item["reviews"])
        for rv in reviews:
            text = rv["review_text"]
            raw = by_text.get((rid, norm(text)))
            if raw is None:
                unmatched += 1
                raw = []
            attrs, seen = [], set()
            for a in raw:
                c = canon(a, inv, bl)
                if c is None:
                    continue
                start = text.lower().find(a["source_text"].lower())  # offsets on the displayed text
                if start < 0:
                    relocated_fail += 1
                    continue
                attrs.append({"dimension": a["dimension"], "entity": a["entity"], "sentiment": a["sentiment"],
                              "polarity": a.get("polarity", "include"), "source_text": a["source_text"],
                              "span": {"start": start, "end": start + len(a["source_text"])},
                              "normalized_entity": c})
                seen.add((a["dimension"], c))
            for d, c in seen:
                support[d][c] += 1
            rv["attributes"] = attrs
        item["reviews"] = reviews
        subj, cats = [], []
        for d in DIMS:
            vals = sorted(v for v, n in support[d].items() if n >= min_support[d])
            item[FIELD[d]] = vals
            kept[d] += len(vals)
            subj += vals
            if vals:
                cats.append(CATEGORY_LABEL[d])
            item[FIELD[d].replace("_attributes", "_support")] = {v: support[d][v] for v in vals}
        item["subjective_attributes"] = subj
        item["subjective_categories"] = cats
        item["subjective_attribute_count"] = len(subj)
        for k in ("subjective_sentiments", "positive_attribute_count", "neutral_attribute_count",
                  "negative_attribute_count"):
            item.pop(k, None)
    df = defaultdict(Counter)
    for item in data["items"]:
        for d in DIMS:
            df[d].update(item[FIELD[d]])
    kept = Counter()
    for item in data["items"]:
        subj = []
        for d in DIMS:
            vals = [v for v in item[FIELD[d]] if df[d][v] >= args.min_recipes]
            item[FIELD[d]] = vals
            item[FIELD[d].replace("_attributes", "_support")] = {v: item[FIELD[d].replace("_attributes", "_support")][v] for v in vals}
            kept[d] += len(vals)
            subj += vals
        item["subjective_attributes"] = subj
        item["subjective_attribute_count"] = len(subj)
        item["subjective_categories"] = [CATEGORY_LABEL[d] for d in DIMS if item[FIELD[d]]]
    print(f"unmatched reviews {unmatched}; spans not found on displayed text {relocated_fail}")
    json.dump(data, open(args.out, "w"))
    print(f"wrote {args.out}; min_support={args.min_support}; recipe-value pairs per dim: {dict(kept)}")


if __name__ == "__main__":
    main()
