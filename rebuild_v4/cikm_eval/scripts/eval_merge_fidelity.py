"""
Normalization Fidelity evaluation: measure the expressiveness-vs-tidiness
trade-off of the synonym mapping step.

Motivation. The agentic normalization loop compresses a long tail of raw
entities into a small set of canonical facet values (good for a clean, browsable
faceted UI). But merging can DISTORT meaning: 'buttery' -> 'creamy', 'meal' ->
'casual'. Plain precision cannot separate "the extractor was wrong" from "the
merge changed the meaning". This script measures the merge step in isolation.

Protocol. We sample only the attributes that the loop actually re-labelled
(entity != normalized_entity), frequency-weighted per dimension so the sample
reflects real database impact. For each, an independent judge (gpt-oss) sees the
review, the source phrase, the ORIGINAL entity, and the CANONICAL form it was
mapped to, and returns a 3-way verdict:

  faithful   - canonical means the same thing in context (hubby -> husband)
  broader    - canonical is more general but not wrong (garlic powder -> garlic)
  distorts   - canonical changes the meaning (buttery -> creamy)

This mirrors canonicalization-quality evaluation for open knowledge bases
(Galarraga et al., CIKM 2014), and is the distortion side of a rate-distortion
view of synonym compression.

Outputs:
  eval_data/merge_fidelity_sample.jsonl
  eval_data/merge_fidelity_results.jsonl
  tables/merge_fidelity.tex
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TABLES = PAPER / "tables"
PROCESSED = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl")

SAMPLE_FILE = EVAL / "merge_fidelity_sample.jsonl"
RESULTS_FILE = EVAL / "merge_fidelity_results.jsonl"
TABLE_FILE = TABLES / "merge_fidelity.tex"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")
REASONING_EFFORT = os.environ.get("JUDGE_REASONING_EFFORT", "low")

DIMS = ["taste_flavor","texture_mouthfeel","meal_type","occasion_holiday","audience_enjoyment","cuisine_type"]
DIM_DISPLAY = {
    "taste_flavor":"Flavor","texture_mouthfeel":"Texture","meal_type":"Meal Type",
    "occasion_holiday":"Occasion","audience_enjoyment":"Audience","cuisine_type":"Cuisine",
}

JUDGE_SYSTEM = """You evaluate whether a synonym-normalization step preserved meaning.
A recipe-review attribute was extracted as an ORIGINAL word/phrase, then a normalization
step replaced it with a CANONICAL form (to merge synonyms for a search filter).
Given the review context, the source phrase, the original, and the canonical, decide:

- "faithful": the canonical means essentially the same thing as the original in this context
  (e.g., hubby -> husband, supper -> dinner, salt -> salty).
- "broader": the canonical is correct but more general / loses some nuance, yet a user
  filtering by the canonical would not be misled (e.g., garlic powder -> garlic, greek -> mediterranean).
- "distorts": the canonical changes or misrepresents the meaning, so a user filtering by the
  canonical would be misled (e.g., buttery -> creamy, meal -> casual, bourbon chicken -> bbq).

Return STRICT JSON only:
{"verdict": "faithful"|"broader"|"distorts", "rationale": "<one short sentence>"}
No prose outside the JSON.
"""


def make_prompt(review, source_text, original, canonical, dim):
    return (
        f"Category: {dim}\n"
        f"Review:\n{review}\n\n"
        f"Source phrase in review: {source_text!r}\n"
        f"ORIGINAL extracted entity: {original!r}\n"
        f"CANONICAL form after normalization: {canonical!r}\n\n"
        f"Output JSON only."
    )


def cmd_sample(args):
    rng = random.Random(args.seed)
    pool = defaultdict(list)
    with open(PROCESSED) as f:
        for line in f:
            r = json.loads(line)
            for a in r["attributes"]:
                e = (a.get("entity") or "").strip().lower()
                ne = (a.get("normalized_entity") or "").strip().lower()
                if e and ne and e != ne:
                    pool[a["dimension"]].append({
                        "recipe_id": r["recipe_id"], "review_idx": r["review_idx"],
                        "review_text": r["review_text"], "dimension": a["dimension"],
                        "source_text": a.get("source_text",""),
                        "original": a["entity"], "canonical": a.get("normalized_entity"),
                    })
    EVAL.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_FILE, "w") as out:
        for d in DIMS:
            items = pool.get(d, [])
            picked = rng.sample(items, min(args.per_category, len(items)))
            for it in picked:
                out.write(json.dumps(it) + "\n")
            print(f"  {d}: sampled {len(picked)}/{len(items)} re-labelled attrs")
    print(f"Wrote {SAMPLE_FILE}")


def call_judge(system, user, retries=3):
    url = API_BASE.rstrip("/") + "/chat/completions"
    payload = {"model": JUDGE_MODEL, "messages": [{"role":"system","content":system},{"role":"user","content":user}],
               "temperature":0.0, "max_tokens":600, "reasoning_effort":REASONING_EFFORT}
    headers = {"Content-Type":"application/json","Authorization":f"Bearer {API_KEY}"}
    text=None
    for attempt in range(retries):
        try:
            resp=requests.post(url,headers=headers,json=payload,timeout=120); resp.raise_for_status()
            text=(resp.json()["choices"][0]["message"].get("content") or "").strip()
            if text.startswith("```"):
                text=text.strip("`")
                if text.lower().startswith("json"): text=text[4:].strip()
            return json.loads(text)
        except Exception as e:
            if attempt==retries-1: return {"error":str(e),"raw":text}
            time.sleep(2**attempt)


def cmd_run(args):
    if not API_KEY or API_KEY=="EMPTY": sys.exit("Set NRP_API_KEY")
    done=set()
    if RESULTS_FILE.exists() and not args.overwrite:
        for line in open(RESULTS_FILE):
            r=json.loads(line); s=r["sample"]
            done.add((s["recipe_id"],s["review_idx"],s["original"],s["dimension"]))
        mode="a"
    else: mode="w"
    pending=[]
    for line in open(SAMPLE_FILE):
        it=json.loads(line)
        if (it["recipe_id"],it["review_idx"],it["original"],it["dimension"]) in done: continue
        pending.append(it)
    n_total=len(pending)+len(done)
    print(f"Resuming: {len(done)} done, {len(pending)} pending, workers={args.workers}",flush=True)
    lock=threading.Lock(); cnt={"d":len(done)}
    def task(it):
        return it, call_judge(JUDGE_SYSTEM, make_prompt(it["review_text"],it["source_text"],it["original"],it["canonical"],it["dimension"]))
    with open(RESULTS_FILE,mode) as fout, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task,it) for it in pending]):
            it,j=fut.result()
            with lock:
                fout.write(json.dumps({"sample":it,"judgment":j})+"\n"); fout.flush()
                cnt["d"]+=1
                v=j.get("verdict","ERR") if "error" not in j else "ERR"
                print(f"  [{cnt['d']}/{n_total}] {it['dimension']:18s} {it['original']!r:22s}->{it['canonical']!r:18s} {v}",flush=True)


def cmd_aggregate(args):
    by=defaultdict(lambda:{"faithful":0,"broader":0,"distorts":0,"err":0,"n":0})
    for line in open(RESULTS_FILE):
        r=json.loads(line); d=r["sample"]["dimension"]; j=r["judgment"]
        if "error" in j: by[d]["err"]+=1; continue
        v=j.get("verdict")
        if v in ("faithful","broader","distorts"):
            by[d][v]+=1; by[d]["n"]+=1
            by["ALL"][v]+=1; by["ALL"]["n"]+=1
    def pct(x,n): return 100*x/n if n else float("nan")
    L=[]; a=L.append
    a("% Auto-generated by scripts/eval_merge_fidelity.py")
    a("\\begin{table}[t]"); a("\\centering"); a("\\small"); a("\\setlength{\\tabcolsep}{4pt}")
    a("\\begin{tabular}{@{}lrrrr@{}}")
    a("\\toprule")
    a("\\textbf{Dimension} & \\textbf{$n$} & \\textbf{Faithful} & \\textbf{Broader} & \\textbf{Distorts} \\\\")
    a(" & & \\textbf{\\%} & \\textbf{\\%} & \\textbf{\\%} \\\\")
    a("\\midrule")
    for d in DIMS:
        s=by[d]
        if s["n"]==0: a(f"{DIM_DISPLAY[d]} & 0 & -- & -- & -- \\\\"); continue
        a(f"{DIM_DISPLAY[d]} & {s['n']} & {pct(s['faithful'],s['n']):.0f} & {pct(s['broader'],s['n']):.0f} & {pct(s['distorts'],s['n']):.0f} \\\\")
    a("\\midrule")
    s=by["ALL"]
    a(f"\\textbf{{All}} & {s['n']} & \\textbf{{{pct(s['faithful'],s['n']):.0f}}} & \\textbf{{{pct(s['broader'],s['n']):.0f}}} & \\textbf{{{pct(s['distorts'],s['n']):.0f}}} \\\\")
    a("\\bottomrule"); a("\\end{tabular}")
    a("\\caption{Normalization fidelity: of the attributes the agentic loop re-labelled "
      "(entity $\\neq$ canonical), what fraction of merges preserve meaning. Sampled "
      "frequency-weighted per dimension; judged by gpt-oss as \\emph{faithful} (same meaning), "
      "\\emph{broader} (more general but not misleading), or \\emph{distorts} (changes meaning). "
      "This is the distortion side of the tidiness--expressiveness trade-off, in the spirit of "
      "open-KB canonicalization quality~\\cite{galarraga2014canonicalizing}. "
      "Faithful+Broader are acceptable for a faceted filter; only Distorts misleads the user.}")
    a("\\label{tab:merge-fidelity}"); a("\\end{table}")
    TABLES.mkdir(parents=True,exist_ok=True)
    TABLE_FILE.write_text("\n".join(L)+"\n")
    print(f"Wrote {TABLE_FILE}\n")
    print(f"{'Dimension':12s} {'n':>4s} {'Faithful':>9s} {'Broader':>8s} {'Distorts':>9s}")
    for d in DIMS+["ALL"]:
        s=by[d]
        if s["n"]==0: continue
        print(f"  {DIM_DISPLAY.get(d,d):10s} {s['n']:4d} {pct(s['faithful'],s['n']):8.0f}% {pct(s['broader'],s['n']):7.0f}% {pct(s['distorts'],s['n']):8.0f}%")


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("sample"); s.add_argument("--per-category",type=int,default=30); s.add_argument("--seed",type=int,default=42)
    r=sub.add_parser("run"); r.add_argument("--workers",type=int,default=8); r.add_argument("--overwrite",action="store_true")
    sub.add_parser("aggregate")
    args=p.parse_args()
    {"sample":cmd_sample,"run":cmd_run,"aggregate":cmd_aggregate}[args.cmd](args)


if __name__=="__main__":
    main()
