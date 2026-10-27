"""Final recipe-level scores on the current v4 exhibit, combining pairs/ and pairs2/ verdicts.

Precision of a set = correct / judged among sampled pairs that are still in that set now
(current top-20 values, current shown membership). KW pairs come from pairs/ (keyword sets do
not depend on the threshold). SER uses SER2 samples for texture and audience (drawn after the
threshold change) and SER samples elsewhere. Estimated correct = pairs x precision.

    python3 rebuild_v4/scripts/score_pairs_final.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
from paper_coverage import DIMS, EXHIBIT, FIELD, TRACE

ROOT = Path(__file__).resolve().parent.parent
items = json.load(open(EXHIBIT))["items"]
byname = {it["name"]: it for it in items}
shown = defaultdict(lambda: defaultdict(set))
for it in items:
    for d in DIMS:
        for v in it[FIELD[d]]:
            shown[d][v].add(it["name"])
cov = json.load(open(ROOT / "data" / "paper_coverage_v4.json"))
judged = []  # (tags, category, facet, recipe, ok)
for sub in ("pairs", "pairs2"):
    key = json.load(open(ROOT / sub / "KEY_do_not_share.json"))
    rows = {r["id"]: r for f in (ROOT / sub).glob("packet_*.json") for r in json.load(open(f))}
    for f in (ROOT / sub).glob("annot_*.json"):
        for j in json.load(open(f))["judgments"]:
            r = rows[j["id"]]
            judged.append((set(key[j["id"]]), r["category"], r["facet"], r["recipe"], j["verdict"] == "correct"))
for k, x in json.load(open(ROOT / "pairs2" / "reused.json")).items():
    d, v, nm = k.split("|")
    judged.append((set(x["tags"]), d, v, nm, x["verdict"] == "correct"))

def prec(pred):
    s = [ok for tags, d, v, nm, ok in judged if pred(tags, d, v, nm)]
    return (sum(s) / len(s) if s else None), len(s)

res, tot = {"table1": {}, "trace": {}}, Counter()
print(f"{'category':20} {'KW pairs':>8} {'KW prec':>8} {'KW est':>7} | {'SER pairs':>9} {'SER prec':>8} {'SER est':>7}  n")
for d in DIMS:
    c = cov["table1"][d]
    top = set(c["facets"])
    pk, nk = prec(lambda t, dd, v, nm: f"KW:{d}" in t)
    sertag = f"SER2:{d}" if d in ("texture_mouthfeel", "audience_enjoyment") else f"SER:{d}"
    ps, ns = prec(lambda t, dd, v, nm: sertag in t and v in top and nm in shown[d][v])
    res["table1"][d] = {"kw": c["kw"], "kw_prec": pk, "ser": c["shown"], "ser_prec": ps, "n_kw": nk, "n_ser": ns}
    tot["kw"] += c["kw"]; tot["ser"] += c["shown"]; tot["ek"] += c["kw"] * pk; tot["es"] += c["shown"] * ps
    print(f"{d:20} {c['kw']:8} {100*pk:7.0f}% {c['kw']*pk:7.0f} | {c['shown']:9} {100*ps:7.0f}% {c['shown']*ps:7.0f}  {nk}/{ns}")
print(f"{'ALL':20} {tot['kw']:8} {100*tot['ek']/tot['kw']:7.0f}% {tot['ek']:7.0f} | {tot['ser']:9} {100*tot['es']/tot['ser']:7.0f}% {tot['es']:7.0f}")
res["all"] = dict(tot)
print("\ntrace        KW rec  KW prec | extracted normalized shown  SER prec  n")
for d, v in TRACE:
    c = cov["trace"][v]
    pk, nk = prec(lambda t, dd, vv, nm: f"KW:trace:{v}" in t)
    tag = f"SER2:trace:{v}" if d in ("texture_mouthfeel", "audience_enjoyment") else f"SER:trace:{v}"
    ps, ns = prec(lambda t, dd, vv, nm: tag in t and nm in shown[d][v])
    res["trace"][v] = {**c, "kw_prec": pk, "ser_prec": ps, "n_kw": nk, "n_ser": ns}
    print(f"{v:12} {c['kw']:6} {100*pk:7.0f}% | {c['extracted']:9} {c['normalized']:10} {c['shown']:5} {100*ps:8.0f}%  {nk}/{ns}")
json.dump(res, open(ROOT / "data" / "paper_numbers_v4.json", "w"), indent=1)
