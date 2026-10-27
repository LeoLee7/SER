"""Unblind the subagent annotations and score old (v3 demo) vs new (v4) per category.

precision = correct / judged tuples of that side.
recall proxy = correct of that side / (correct of either side + missed by both).

    python3 rebuild_v4/scripts/score_blind.py [blind_dir]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

d = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "blind")
key = json.load(open(d / "KEY_do_not_share.json"))
cat_of, judg, missed = {}, {}, Counter()
for p in sorted(d.glob("packet_*.json")):
    for rv in json.load(open(p)):
        for t in rv["tuples"]:
            cat_of[t["id"]] = t["category"]
for a in sorted(d.glob("annot_*.json")):
    ann = json.load(open(a))
    for j in ann["judgments"]:
        judg[j["id"]] = j
    for m in ann["missed"]:
        missed[m["category"]] += 1

missing = set(cat_of) - set(judg)
stats = defaultdict(lambda: Counter())
codes = {"old": Counter(), "new": Counter()}
for tid, j in judg.items():
    c, ok = cat_of[tid], j["verdict"] == "correct"
    for cat in (c, "ALL"):
        stats[cat]["any_ok"] += ok
        for side in key[tid]:
            stats[cat][side + "_n"] += 1
            stats[cat][side + "_ok"] += ok
    if not ok:
        for side in key[tid]:
            codes[side][j.get("code")] += 1
for c, n in missed.items():
    stats[c]["missed"] += n
    stats["ALL"]["missed"] += n

print(f"{'category':20} {'old prec':>9} {'old rec':>8} {'old ok/n':>9} | {'new prec':>9} {'new rec':>8} {'new ok/n':>9} | missed")
for c in ["taste_flavor", "texture_mouthfeel", "meal_type", "occasion_holiday", "audience_enjoyment", "cuisine_type", "ALL"]:
    s = stats[c]
    pool = s["any_ok"] + s["missed"]
    row = []
    for side in ("old", "new"):
        row.append(f"{100 * s[side + '_ok'] / max(s[side + '_n'], 1):8.0f}% {100 * s[side + '_ok'] / max(pool, 1):7.0f}% {s[side + '_ok']:4}/{s[side + '_n']:<4}")
    print(f"{c:20} {row[0]} | {row[1]} | {s['missed']}")
print("wrong codes old:", codes["old"].most_common(6))
print("wrong codes new:", codes["new"].most_common(6))
if missing:
    print("UNJUDGED ids:", len(missing))
