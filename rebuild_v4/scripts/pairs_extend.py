"""Extend the recipe-level eval after the threshold change (texture, audience -> 1).

Samples SER pairs from the current v4 exhibit for the given categories and traced facets,
reuses verdicts for pairs already judged in pairs/, and writes unseen ones to pairs2/.
Tags are written so score_pairs_final.py can compute precision on the current SER set.

    python3 rebuild_v4/scripts/pairs_extend.py
"""
import json, random, re
from collections import defaultdict
from pathlib import Path
import make_pair_eval as M
from paper_coverage import DIMS, EXHIBIT, FIELD, TRACE

ROOT = Path(__file__).resolve().parent.parent
random.seed(26)
items = {it["id"]: it for it in json.load(open(EXHIBIT))["items"]}
name = {rid: it["name"] for rid, it in items.items()}
shown = defaultdict(lambda: defaultdict(set))
for rid, it in items.items():
    for d in DIMS:
        for v in it[FIELD[d]]:
            shown[d][v].add(rid)
# verdict cache from round 1, keyed by (category, facet, recipe name)
cache = {}
for f in (ROOT / "pairs").glob("packet_*.json"):
    for r in json.load(open(f)):
        cache[(r["category"], r["facet"], r["recipe"])] = r["id"]
verd = {j["id"]: j["verdict"] for f in (ROOT / "pairs").glob("annot_*.json") for j in json.load(open(f))["judgments"]}
sel = []  # (tag, d, v, rid)
for d in ("texture_mouthfeel", "audience_enjoyment"):
    top = sorted(shown[d], key=lambda v: -len(shown[d][v]))[:20]
    pool = [(v, r) for v in top for r in shown[d][v]]
    sel += [(f"SER2:{d}", d, v, r) for v, r in random.sample(pool, 60)]
for d, v in TRACE:
    if d in ("texture_mouthfeel", "audience_enjoyment"):
        sel += [(f"SER2:trace:{v}", d, v, r) for r in random.sample(sorted(shown[d][v]), 30)]
reused, todo = {}, {}
for tag, d, v, r in sel:
    k = (d, v, name[r])
    if k in cache:
        reused.setdefault(k, set()).add(tag)
    else:
        todo.setdefault(k, {"tags": set(), "rid": r})["tags"].add(tag)
# evidence builder from make_pair_eval
pat_cache = {}
def evidence(d, v, rid):
    pat = re.compile(r"\b" + re.escape(v.lower()) + r"\b")
    linked, word = [], []
    for rv in items[rid]["reviews"]:
        spans = [a["source_text"].lower() for a in rv["attributes"] if a["dimension"] == d and a["normalized_entity"] == v]
        for s in M.sentences(rv["review_text"]):
            if any(sp in s.lower() for sp in spans): linked.append(s[:400])
            elif pat.search(s.lower()): word.append(s[:400])
    return (linked + word)[:10]
out = ROOT / "pairs2"; out.mkdir(exist_ok=True)
rows, key = [], {}
for i, ((d, v, nm), x) in enumerate(todo.items()):
    pid = f"q{i:04d}"; key[pid] = sorted(x["tags"])
    rows.append({"id": pid, "category": d, "facet": v, "recipe": nm, "evidence": evidence(d, v, x["rid"])})
random.shuffle(rows)
json.dump(key, open(out / "KEY_do_not_share.json", "w"))
json.dump({"|".join(k): {"id": cache[k], "verdict": verd[cache[k]], "tags": sorted(t)} for k, t in reused.items()}, open(out / "reused.json", "w"), indent=1)
half = -(-len(rows) // 2)
for g in range(2): json.dump(rows[g * half:(g + 1) * half], open(out / f"packet_{g}.json", "w"), indent=1)
print(f"{len(sel)} sampled, {len(reused)} reused, {len(rows)} new")
