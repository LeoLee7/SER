"""Coverage for the paper tables on the v4 recipe instance (same definitions as the CIKM tables).

KW: recipes with at least one displayed review containing the facet word as a whole word or phrase.
Extracted: recipes with at least one extraction whose own surface value equals the facet (no merging).
Normalized: recipes with at least one extraction mapped to the facet by the v4 synonym map.
Shown: recipes carrying the facet in the demo (normalized + per-category support threshold).
Table 1 sums facet-recipe pairs over each category's 20 most frequent shown facets.

    python3 rebuild_v4/scripts/paper_coverage.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

from observe import DIMS, canon, load_maps

ROOT = Path(__file__).resolve().parent.parent
EXHIBIT = ROOT / "data" / "food-exhibit-data-500recipes.v4.json"
FIELD = {"taste_flavor": "taste_attributes", "texture_mouthfeel": "texture_attributes",
         "meal_type": "meal_type_attributes", "occasion_holiday": "occasion_attributes",
         "audience_enjoyment": "audience_attributes", "cuisine_type": "type_attributes"}
TRACE = [("taste_flavor", "tangy"), ("texture_mouthfeel", "crispy"), ("occasion_holiday", "holiday"),
         ("audience_enjoyment", "kids"), ("cuisine_type", "Mexican")]


def main():
    inv, bl = load_maps()
    items = json.load(open(EXHIBIT))["items"]
    text = {it["id"]: " ".join(rv["review_text"] for rv in it["reviews"]).lower() for it in items}
    shown, normalized, extracted = (defaultdict(lambda: defaultdict(set)) for _ in range(3))
    by_text = {}
    for line in open(ROOT / "data" / "verified_v4.jsonl"):
        r = json.loads(line)
        by_text[(str(r["recipe_id"]), re.sub(r"\s+", " ", r["review_text"]).strip())] = r["attributes"]
    for it in items:
        for d in DIMS:
            for v in it[FIELD[d]]:
                shown[d][v].add(it["id"])
        for rv in it["reviews"]:
            for a in rv["attributes"]:
                normalized[a["dimension"]][a["normalized_entity"]].add(it["id"])
                extracted[a["dimension"]][a["entity"].strip().lower()].add(it["id"])

    def kw(value):
        pat = re.compile(r"\b" + re.escape(value.lower()) + r"\b")
        return {i for i, t in text.items() if pat.search(t)}

    out = {"table1": {}, "trace": {}}
    print(f"{'category':20} {'KW':>6} {'norm':>6} {'shown':>6}   (pairs over top-20 shown facets)")
    for d in DIMS:
        top = sorted(shown[d], key=lambda v: -len(shown[d][v]))[:20]
        k = sum(len(kw(v)) for v in top)
        n = sum(len(normalized[d][v]) for v in top)
        s = sum(len(shown[d][v]) for v in top)
        out["table1"][d] = {"facets": top, "kw": k, "normalized": n, "shown": s}
        print(f"{d:20} {k:6} {n:6} {s:6}")
    print("\ntrace facet           KW  extracted  normalized  shown")
    for d, v in TRACE:
        row = {"kw": len(kw(v)), "extracted": len(extracted[d][v.lower()]),
               "normalized": len(normalized[d][v]), "shown": len(shown[d][v])}
        out["trace"][v] = row
        print(f"{d[:10]:10} {v:9} {row['kw']:5} {row['extracted']:9} {row['normalized']:11} {row['shown']:6}")
    json.dump(out, open(ROOT / "data" / "paper_coverage_v4.json", "w"), indent=1)


if __name__ == "__main__":
    main()
