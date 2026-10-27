"""Observe step of the normalization loop: frequency-sorted values per category after the
current synonym map and blacklist, with coverage stats and an example span per value.

    python3 rebuild_v4/scripts/observe.py ROUND_NAME [--top 120]
Writes normalization/observe_ROUND_NAME.md.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIMS = ["taste_flavor", "texture_mouthfeel", "meal_type", "occasion_holiday", "audience_enjoyment", "cuisine_type"]


def load_maps():
    syn = json.load(open(ROOT / "data" / "synonyms_v4.json")) if (ROOT / "data" / "synonyms_v4.json").exists() else {}
    bl = json.load(open(ROOT / "data" / "blacklist_v4.json")) if (ROOT / "data" / "blacklist_v4.json").exists() else {}
    inv = {d: {v.lower(): canon for canon, vs in syn.get(d, {}).items() for v in vs + [canon]} for d in DIMS}
    return inv, {d: {v.lower() for v in bl.get(d, [])} for d in DIMS}


def canon(a, inv, bl):
    e = a["entity"].strip().lower()
    c = inv[a["dimension"]].get(e, e)
    return None if c.lower() in bl[a["dimension"]] else c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("round")
    ap.add_argument("--top", type=int, default=120)
    ap.add_argument("--src", default=str(ROOT / "data" / "verified_v4.jsonl"))
    args = ap.parse_args()
    inv, bl = load_maps()
    mentions, recipes, example = defaultdict(Counter), defaultdict(lambda: defaultdict(set)), {}
    for line in open(args.src):
        r = json.loads(line)
        for a in r["attributes"]:
            c = canon(a, inv, bl)
            if c is None:
                continue
            mentions[a["dimension"]][c] += 1
            recipes[a["dimension"]][c].add(r["recipe_id"])
            example.setdefault((a["dimension"], c), a["source_text"])
    out = [f"# Observe {args.round}\n"]
    for d in DIMS:
        m = mentions[d]
        total = sum(m.values())
        top30 = sum(n for _, n in m.most_common(30))
        out.append(f"\n## {d}: {len(m)} values, {total} mentions, top-30 cover {100 * top30 / max(total, 1):.1f}%\n")
        out.append("| value | mentions | recipes | example |\n|---|---|---|---|")
        for v, n in m.most_common(args.top):
            out.append(f"| {v} | {n} | {len(recipes[d][v])} | {example[(d, v)][:70]} |")
    path = ROOT / "normalization" / f"observe_{args.round}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(out))
    for d in DIMS:
        m = mentions[d]
        total = sum(m.values())
        print(f"{d:20} values={len(m):5} mentions={total:6} top30={100 * sum(n for _, n in m.most_common(30)) / max(total, 1):.1f}%")


if __name__ == "__main__":
    main()
