"""Score one grounded extraction file against all blind verdicts collected so far.

Verdict cache = every (review, category, value) judged in blind*/ (subagents or Claude).
precision = correct / judged; recall proxy = correct / (all correct values for those reviews
from any version + values annotators listed as missed). Unjudged items are reported, not guessed.

    python3 rebuild_v4/scripts/score_file.py FILE [FILE ...]
"""
import glob, json, sys
from collections import Counter, defaultdict
from pathlib import Path
B = Path(__file__).resolve().parent.parent
cache, pool, rev_set = {}, defaultdict(set), set()
for d in sorted(glob.glob(str(B / "blind*"))):
    P = {t["id"]: (t, r["review"].strip()) for f in glob.glob(d + "/packet_*.json") for r in json.load(open(f)) for t in r["tuples"]}
    for f in glob.glob(d + "/annot_*.json"):
        a = json.load(open(f))
        rid2text = {r["review_id"]: r["review"].strip() for pf in glob.glob(d + "/packet_*.json") for r in json.load(open(pf))}
        for j in a["judgments"]:
            t, rv = P[j["id"]]
            k = (rv, t["category"], t["value"].lower())
            cache[k] = j["verdict"] == "correct"
            rev_set.add(rv)
            if cache[k]:
                pool[t["category"]].add(k)
        for m in a["missed"]:
            pool[m["category"]].add((rid2text[m["review_id"]], m["category"], m["value"].lower()))
DIMS = ["taste_flavor", "texture_mouthfeel", "meal_type", "occasion_holiday", "audience_enjoyment", "cuisine_type"]
for path in sys.argv[1:]:
    s, unj = defaultdict(Counter), 0
    for line in open(path):
        r = json.loads(line)
        rv = r["review_text"].strip()
        if rv not in rev_set:
            continue
        seen = set()
        for a in r["attributes"]:
            k = (rv, a["dimension"], a["entity"].lower())
            if k in seen: continue
            seen.add(k)
            if k not in cache: unj += 1; continue
            for c in (a["dimension"], "ALL"):
                s[c]["n"] += 1; s[c]["ok"] += cache[k]
    pool_all = sum(len(v) for v in pool.values())
    print(f"{Path(path).name}   (unjudged {unj})")
    for c in DIMS + ["ALL"]:
        p = pool_all if c == "ALL" else len(pool[c])
        print(f"   {c:20} prec {100*s[c]['ok']/max(s[c]['n'],1):4.0f}% ({s[c]['ok']}/{s[c]['n']})   recall {100*s[c]['ok']/max(p,1):4.0f}% (of {p})")
