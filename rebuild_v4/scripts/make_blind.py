"""Build blind annotation packets comparing two exhibit JSONs on the same displayed reviews.

Tuples are the facet values each version shows for a review (normalized_entity), with evidence.
Identical (category, value) pairs from both sides are judged once and credited to both.

    python3 rebuild_v4/scripts/make_blind.py OLD.json NEW.json OUT_DIR --n 100 --seed 11 --exclude ids.json ...
"""
import argparse
import json
import random
from pathlib import Path


def reviews(path):
    out = {}
    for item in json.load(open(path))["items"]:
        for rv in item["reviews"]:
            out[(str(item["id"]), rv["review_text"].strip())] = (item["name"], rv["attributes"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("out")
    ap.add_argument("--n", type=int, default=100); ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--packets", type=int, default=4)
    ap.add_argument("--exclude-texts", nargs="*", default=[], help="jsonl files whose review_text values to exclude")
    args = ap.parse_args()
    old, new = reviews(args.old), reviews(args.new)
    excluded = {json.loads(l)["review_text"].strip() for f in args.exclude_texts for l in open(f)}
    keys = sorted(k for k in old if k in new and k[1] not in excluded)
    random.seed(args.seed)
    sample = random.sample(keys, args.n)
    key, packets = {}, []
    for i, k in enumerate(sample):
        merged = {}
        for side, src in (("old", old), ("new", new)):
            for a in src[k][1]:
                v = a.get("normalized_entity") or a["entity"]
                m = merged.setdefault((a["dimension"], v.lower()), {"d": a["dimension"], "v": v, "e": a["source_text"], "sides": set()})
                m["sides"].add(side)
        items = list(merged.values())
        random.shuffle(items)
        tuples = []
        for j, m in enumerate(items):
            tid = f"h{i:03d}_t{j:02d}"
            key[tid] = sorted(m["sides"])
            tuples.append({"id": tid, "category": m["d"], "value": m["v"], "evidence": m["e"]})
        packets.append({"review_id": f"h{i:03d}", "recipe": old[k][0], "review": k[1], "tuples": tuples})
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    json.dump(key, open(out / "KEY_do_not_share.json", "w"))
    size = -(-len(packets) // args.packets)
    for g in range(args.packets):
        json.dump(packets[g * size:(g + 1) * size], open(out / f"packet_{g}.json", "w"), indent=1)
    print(f"{len(packets)} reviews, {len(key)} tuples, {sum(len(v) == 2 for v in key.values())} shared")


if __name__ == "__main__":
    main()
