"""Recipe-level blind eval: is this recipe correctly returned for this facet?

Pairs (facet, recipe) are sampled from three sets per category, over the top-20 shown facets:
  KW      recipe has a displayed review containing the facet word,
  SER     recipe carries the facet in the v4 demo,
  CUT     recipe has v4 mentions of the facet but falls below the support threshold.
Plus the five traced facets of Table 2 (KW and SER). The annotator sees one evidence list per
pair: every review sentence that contains the word or holds a v4 span for the facet, unlabeled,
so a pair gets the same verdict whichever method returned it.

    python3 rebuild_v4/scripts/make_pair_eval.py
"""
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from paper_coverage import DIMS, EXHIBIT, FIELD, TRACE

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pairs"
SENT = re.compile(r"(?<=[.!?])\s+|<br\s*/?>|\n")
N_CAT, N_CUT, N_TRACE = 40, 20, 30
DENSE = {"taste_flavor", "texture_mouthfeel", "audience_enjoyment"}


def sentences(text):
    return [s.strip() for s in SENT.split(text) if s and s.strip()]


def main():
    random.seed(25)
    items = {it["id"]: it for it in json.load(open(EXHIBIT))["items"]}
    shown, mentioned = defaultdict(lambda: defaultdict(set)), defaultdict(lambda: defaultdict(set))
    for rid, it in items.items():
        for d in DIMS:
            for v in it[FIELD[d]]:
                shown[d][v].add(rid)
        for rv in it["reviews"]:
            for a in rv["attributes"]:
                mentioned[a["dimension"]][a["normalized_entity"]].add(rid)

    def kw_set(v):
        pat = re.compile(r"\b" + re.escape(v.lower()) + r"\b")
        return {rid for rid, it in items.items() if any(pat.search(rv["review_text"].lower()) for rv in it["reviews"])}

    def evidence(d, v, rid):
        pat = re.compile(r"\b" + re.escape(v.lower()) + r"\b")
        linked, word = [], []
        for rv in items[rid]["reviews"]:
            spans = [a["source_text"].lower() for a in rv["attributes"] if a["dimension"] == d and a["normalized_entity"] == v]
            for s in sentences(rv["review_text"]):
                if any(sp in s.lower() for sp in spans):
                    linked.append(s[:400])
                elif pat.search(s.lower()):
                    word.append(s[:400])
        return (linked + word)[:10]  # linked sentences first so a cap never hides them

    pairs, membership = {}, defaultdict(set)

    def add(tag, d, v, rid):
        key = (d, v, rid)
        membership[key].add(tag)
        if key not in pairs:
            pairs[key] = evidence(d, v, rid)

    for d in DIMS:
        top = sorted(shown[d], key=lambda v: -len(shown[d][v]))[:20]
        kw_pool = [(v, r) for v in top for r in kw_set(v)]
        ser_pool = [(v, r) for v in top for r in shown[d][v]]
        cut_pool = [(v, r) for v in top for r in mentioned[d][v] - shown[d][v]]
        for tag, pool, n in (("KW", kw_pool, N_CAT), ("SER", ser_pool, N_CAT), ("CUT", cut_pool, N_CUT if d in DENSE else 0)):
            for v, r in random.sample(pool, min(n, len(pool))):
                add(f"{tag}:{d}", d, v, r)
    for d, v in TRACE:
        for tag, pool in (("KW", sorted(kw_set(v))), ("SER", sorted(shown[d][v]))):
            for r in random.sample(pool, min(N_TRACE, len(pool))):
                add(f"{tag}:trace:{v}", d, v, r)

    keys = list(pairs)
    random.shuffle(keys)
    OUT.mkdir(exist_ok=True)
    rows = [{"id": f"p{i:04d}", "category": d, "facet": v, "recipe": items[r]["name"],
             "evidence": pairs[(d, v, r)]} for i, (d, v, r) in enumerate(keys)]
    json.dump({f"p{i:04d}": sorted(membership[k]) for i, k in enumerate(keys)}, open(OUT / "KEY_do_not_share.json", "w"))
    size = -(-len(rows) // 6)
    for g in range(6):
        json.dump(rows[g * size:(g + 1) * size], open(OUT / f"packet_{g}.json", "w"), indent=1)
    print(f"{len(rows)} unique pairs in 6 packets")


if __name__ == "__main__":
    main()
