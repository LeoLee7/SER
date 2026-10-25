"""Score the recipe-level blind eval (pairs/).

For each set (KW, SER, CUT) and category: precision = correct / judged sampled pairs, and
estimated correct pairs = all pairs in that set x precision (pair totals from paper_coverage).

    python3 rebuild_v4/scripts/score_pairs.py
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "pairs"
key = json.load(open(P / "KEY_do_not_share.json"))
verdict = {j["id"]: j["verdict"] == "correct" for f in sorted(P.glob("annot_*.json")) for j in json.load(open(f))["judgments"]}
cov = json.load(open(ROOT / "data" / "paper_coverage_v4.json"))
stats = defaultdict(Counter)
for pid, tags in key.items():
    if pid not in verdict:
        continue
    for t in tags:
        stats[t]["n"] += 1
        stats[t]["ok"] += verdict[pid]
missing = len(key) - len(verdict)

def prec(tag):
    s = stats[tag]
    return s["ok"] / s["n"] if s["n"] else None

result = {"categories": {}, "trace": {}}
print(f"{'category':20} {'KW pairs':>8} {'KW prec':>8} {'KW est':>7} | {'SER pairs':>9} {'SER prec':>8} {'SER est':>7} | {'CUT prec':>8}")
tot = Counter()
for d, c in cov["table1"].items():
    pk, ps, pc = prec(f"KW:{d}"), prec(f"SER:{d}"), prec(f"CUT:{d}")
    ek, es = c["kw"] * pk, c["shown"] * ps
    tot["kw"] += c["kw"]; tot["shown"] += c["shown"]; tot["ek"] += ek; tot["es"] += es
    result["categories"][d] = {"kw_pairs": c["kw"], "kw_prec": pk, "kw_est": ek, "ser_pairs": c["shown"], "ser_prec": ps,
                               "ser_est": es, "cut_prec": pc, "n": [stats[f"KW:{d}"]["n"], stats[f"SER:{d}"]["n"], stats[f"CUT:{d}"]["n"]]}
    cut = f"{100 * pc:7.0f}%" if pc is not None else "      -"
    print(f"{d:20} {c['kw']:8} {100 * pk:7.0f}% {ek:7.0f} | {c['shown']:9} {100 * ps:7.0f}% {es:7.0f} | {cut}")
print(f"{'ALL':20} {tot['kw']:8} {100 * tot['ek'] / tot['kw']:7.0f}% {tot['ek']:7.0f} | {tot['shown']:9} {100 * tot['es'] / tot['shown']:7.0f}% {tot['es']:7.0f}")
print("\ntrace facet   KW recipes  KW prec  KW est | SER recipes  SER prec  SER est")
for v, c in cov["trace"].items():
    pk, ps = prec(f"KW:trace:{v}"), prec(f"SER:trace:{v}")
    result["trace"][v] = {**c, "kw_prec": pk, "ser_prec": ps, "n": [stats[f"KW:trace:{v}"]["n"], stats[f"SER:trace:{v}"]["n"]]}
    print(f"{v:12} {c['kw']:10} {100 * pk:7.0f}% {c['kw'] * pk:6.0f} | {c['shown']:11} {100 * ps:8.0f}% {c['shown'] * ps:7.0f}")
if missing:
    print("unjudged pairs:", missing)
json.dump(result, open(ROOT / "data" / "pair_eval_v4.json", "w"), indent=1)
