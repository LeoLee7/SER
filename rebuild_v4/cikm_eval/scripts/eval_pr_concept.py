"""
Pooled precision-recall across the pipeline gradient, per concept.

For a concept (e.g., "spicy"), four retrieval methods each return a set of recipes:
  (1) keyword  - reviews literally contain the exact concept word
  (2) gemma    - Gemma-3 raw extracted entity == concept (pre-normalization)
  (3) v1       - normalized_entity == concept (after agentic normalization)
  (4) v2       - v1 surviving the judge-feedback blacklist + non-negative sentiment

We pool the union of all four sets and obtain an INDEPENDENT gold label per recipe:
an LLM judge reads the review evidence and decides whether the concept genuinely
applies (handling nuance: "too spicy" => spicy DOES apply; "not spicy" => does NOT).
Then per method we compute pooled precision and recall against that gold.

This places all four stages on one precision-recall plane and shows the
trajectory: keyword = high recall / low precision (negations), gemma = high
precision / lower recall, +normalization recovers recall, +judge lifts precision.

Standard pooling assumption (TREC): relevant recipes outside the pool are
assumed negligible, so recall is pooled recall.

Usage:
  python3 scripts/eval_pr_concept.py build
  python3 scripts/eval_pr_concept.py judge --workers 8
  python3 scripts/eval_pr_concept.py aggregate
"""
from __future__ import annotations
import argparse, json, os, re, sys, threading, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT = Path("/Users/liliu/SER-DB")
PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TABLES = PAPER / "tables"
TRULYRAW = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
PROC = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl")
BL_FILE = ROOT / "attribute_blacklist.json"
POOL_FILE = EVAL / "pr_concept_pool.jsonl"
JUDG_FILE = EVAL / "pr_concept_judgments.jsonl"
TABLE_FILE = TABLES / "pr_concept.tex"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")
REASONING_EFFORT = os.environ.get("JUDGE_REASONING_EFFORT", "low")

# concept -> (dimension, intent, surface forms for evidence snippets)
CONCEPTS = {
    "spicy": ("taste_flavor",
              "the dish is genuinely spicy/hot in flavor",
              ["spicy","heat","hot","kick","fiery","peppery"]),
    "mother": ("audience_enjoyment",
               "a reviewer indicates a mother enjoys or relates to the dish",
               ["mother","mom","mum","mommy","mama","momma"]),
    "kids": ("audience_enjoyment",
             "a reviewer indicates children/kids enjoy the dish",
             ["kids","kid","child","children","toddler","little ones"]),
    "husband": ("audience_enjoyment",
             "a reviewer indicates a husband enjoys or relates to the dish",
             ["husband","hubby","dh","hubs","hubbie"]),
    "tangy": ("taste_flavor",
             "the dish is genuinely tangy / tart / zesty in flavor",
             ["tangy","tart","tartness","zesty","zingy","tang"]),
    "game-day": ("occasion_holiday",
             "the dish is meant for a game-day / sports-watching occasion",
             ["game-day","game day","super bowl","football game","game night","tailgate"]),
    "mediterranean": ("cuisine_type",
             "the dish is Mediterranean cuisine",
             ["mediterranean","greek"]),
}


def load_all():
    reviews = defaultdict(list)
    gemma = defaultdict(lambda: defaultdict(set))   # rid -> dim -> set(entity)
    seen=set()
    for line in open(TRULYRAW):
        r=json.loads(line); rid=r["recipe_id"]; ridx=r["review_idx"]
        if (rid,ridx) not in seen:
            reviews[rid].append(r["review_text"]); seen.add((rid,ridx))
        for a in r["attributes"]:
            gemma[rid][a["dimension"]].add((a.get("entity") or "").strip().lower())
    v1=defaultdict(lambda: defaultdict(set)); v2=defaultdict(lambda: defaultdict(set))
    bl=json.load(open(BL_FILE))
    for line in open(PROC):
        r=json.loads(line); rid=r["recipe_id"]
        for a in r["attributes"]:
            d=a["dimension"]; ne=(a.get("normalized_entity") or "").strip().lower()
            if not ne: continue
            v1[rid][d].add(ne)
            blk=set(x.lower() for x in bl.get(d,[]))|set(x.lower() for x in bl.get("global",[]))
            if ne in blk or a.get("sentiment")=="negative": continue
            v2[rid][d].add(ne)
    return reviews, gemma, v1, v2, bl


def method_sets(concept, dim, reviews, gemma, v1, v2):
    word=concept.lower()
    pat=re.compile(r"\b"+re.escape(word)+r"\b", re.I)
    kw={rid for rid,rv in reviews.items() if any(pat.search(t) for t in rv)}
    g ={rid for rid,dd in gemma.items() if word in dd.get(dim,set())}
    a1={rid for rid,dd in v1.items() if word in dd.get(dim,set())}
    a2={rid for rid,dd in v2.items() if word in dd.get(dim,set())}
    return {"keyword":kw,"gemma":g,"v1":a1,"v2":a2}


def snippets(reviews_for_recipe, surfaces, maxn=3, win=90):
    pat=re.compile(r"\b("+"|".join(re.escape(s) for s in surfaces)+r")\b", re.I)
    out=[]
    for t in reviews_for_recipe:
        for m in pat.finditer(t):
            s=t[max(0,m.start()-win):m.end()+30].replace("\n"," ").strip()
            out.append(s)
            if len(out)>=maxn: return out
    return out


def cmd_build(args):
    reviews, gemma, v1, v2, bl = load_all()
    pairs=[]
    summary={}
    for concept,(dim,intent,surf) in CONCEPTS.items():
        sets=method_sets(concept, dim, reviews, gemma, v1, v2)
        pool=set().union(*sets.values())
        summary[concept]={k:len(v) for k,v in sets.items()} | {"pool":len(pool)}
        for rid in pool:
            snip=snippets(reviews.get(rid,[]), surf)
            pairs.append({
                "concept":concept,"dim":dim,"intent":intent,"recipe_id":rid,
                "snippets":snip,
                "in":{k:(rid in s) for k,s in sets.items()},
            })
    EVAL.mkdir(parents=True,exist_ok=True)
    with open(POOL_FILE,"w") as f:
        for p in pairs: f.write(json.dumps(p)+"\n")
    print("Per-concept method set sizes and pool:")
    for c,s in summary.items():
        print(f"  {c:8s} kw={s['keyword']} gemma={s['gemma']} v1={s['v1']} v2={s['v2']} | pool={s['pool']}")
    print(f"Total recipe-concept pairs to judge: {len(pairs)}")
    print(f"Wrote {POOL_FILE}")


JUDGE_SYS="""You decide whether a concept genuinely applies to a recipe, based on review evidence.
Handle nuance carefully:
- "too spicy", "very spicy", "a bit spicy" => spicy DOES apply (it is spicy).
- "not spicy", "wasn't spicy", "could be spicier", "not spicy enough" => spicy does NOT apply.
- For audience concepts (mother/kids): the concept applies if a reviewer indicates that
  person enjoyed / would enjoy / is connected to the dish (e.g., "my mom loved this",
  "my kids devoured it"). It does NOT apply if merely mentioned irrelevantly or negated
  ("my kids wouldn't touch it" => kids do NOT apply as enjoying it).
Return STRICT JSON only: {"applies": true|false, "reason":"<short>"}"""

def make_prompt(p):
    snip="\n".join(f"  - {s}" for s in p["snippets"]) or "  (no snippet found)"
    return (f"Concept: {p['concept']} ({p['intent']})\n"
            f"Review evidence from this recipe:\n{snip}\n\nDoes the concept genuinely apply? JSON only.")

def call_judge(user, retries=3):
    url=API_BASE.rstrip('/')+"/chat/completions"
    payload={"model":JUDGE_MODEL,"messages":[{"role":"system","content":JUDGE_SYS},{"role":"user","content":user}],
             "temperature":0.0,"max_tokens":400,"reasoning_effort":REASONING_EFFORT}
    h={"Content-Type":"application/json","Authorization":f"Bearer {API_KEY}"}
    text=None
    for a in range(retries):
        try:
            r=requests.post(url,headers=h,json=payload,timeout=120); r.raise_for_status()
            text=(r.json()["choices"][0]["message"].get("content") or "").strip()
            if text.startswith("```"):
                text=text.strip("`")
                if text.lower().startswith("json"): text=text[4:].strip()
            return json.loads(text)
        except Exception as e:
            if a==retries-1: return {"error":str(e),"raw":text}
            time.sleep(2**a)

def cmd_judge(args):
    if not API_KEY or API_KEY=="EMPTY": sys.exit("Set NRP_API_KEY")
    pairs=[json.loads(l) for l in open(POOL_FILE)]
    done=set()
    if JUDG_FILE.exists() and not args.overwrite:
        for l in open(JUDG_FILE):
            r=json.loads(l); done.add((r["concept"],r["recipe_id"]))
        mode="a"
    else: mode="w"
    pend=[p for p in pairs if (p["concept"],p["recipe_id"]) not in done]
    print(f"Judging {len(pend)} pairs (workers={args.workers})",flush=True)
    lock=threading.Lock(); c={"n":len(done)}; tot=len(pairs)
    def task(p): return p, call_judge(make_prompt(p))
    with open(JUDG_FILE,mode) as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task,p) for p in pend]):
            p,j=fut.result()
            with lock:
                f.write(json.dumps({"concept":p["concept"],"recipe_id":p["recipe_id"],"in":p["in"],"snippets":p["snippets"],"judgment":j})+"\n"); f.flush()
                c["n"]+=1
                if c["n"]%50==0: print(f"  {c['n']}/{tot}",flush=True)

def cmd_aggregate(args):
    rows=[json.loads(l) for l in open(JUDG_FILE)]
    methods=["keyword","gemma","v1","v2"]
    DISP={"keyword":"(1) Keyword","gemma":"(2) Gemma extract","v1":"(3) +Normalize","v2":"(4) +Judge fb"}
    # per concept
    L=[]; a=L.append
    a("% Auto-generated by scripts/eval_pr_concept.py")
    a("\\begin{table}[t]"); a("\\centering"); a("\\small"); a("\\setlength{\\tabcolsep}{4pt}")
    a("\\begin{tabular}{@{}ll rr r@{}}")
    a("\\toprule")
    a("\\textbf{Concept} & \\textbf{Stage} & \\textbf{P\\%} & \\textbf{R\\%} & \\textbf{F1} \\\\")
    a("\\midrule")
    console=[]
    err_cases=defaultdict(list)
    for concept in CONCEPTS:
        cr=[r for r in rows if r["concept"]==concept and "error" not in r["judgment"]]
        gold={r["recipe_id"] for r in cr if r["judgment"].get("applies")}
        for mi,m in enumerate(methods):
            ret={r["recipe_id"] for r in cr if r["in"].get(m)}
            tp=len(ret&gold);
            P=100*tp/len(ret) if ret else 0
            R=100*tp/len(gold) if gold else 0
            F=2*P*R/(P+R) if P+R else 0
            last = (mi==len(methods)-1)
            a(f"{'' if mi else concept} & {DISP[m]} & {P:.0f} & {R:.0f} & {F:.0f} \\\\" + ("" if not last else ""))
            console.append((concept,m,len(ret),tp,len(gold),P,R,F))
        a("\\midrule")
        # collect keyword false positives (returned by keyword, judged not-apply) for error analysis
        for r in cr:
            if r["in"].get("keyword") and not r["judgment"].get("applies"):
                err_cases[concept].append((r["recipe_id"], r["snippets"][:1], r["judgment"].get("reason","")))
    a("\\bottomrule"); a("\\end{tabular}")
    a("\\caption{Pooled precision/recall across the pipeline for three concepts. "
      "Gold = an independent LLM judge ruling whether the concept genuinely applies, "
      "handling negation and irrelevant mentions (e.g.\\ ``not spicy'', ``spicy mustard'' "
      "as an ingredient, ``my mother used to make it''). "
      "Precision is essentially flat across stages (2)--(4): the pipeline relabels and "
      "filters but never re-verifies an individual extraction, so per-item correctness "
      "is set by the extractor. The pipeline's gain is on \\emph{recall}: LLM extraction "
      "already understands surface synonyms (mother: $49\\!\\to\\!95$) and normalization "
      "merges the remaining variants (spicy: $76\\!\\to\\!90$, kids: $92\\!\\to\\!99$). "
      "Keyword precision is concept-dependent (low for \\emph{mother}, 41\\%, where "
      "mentions are often irrelevant; high for \\emph{kids}, 81\\%). Pooled recall (TREC assumption).}")
    a("\\label{tab:pr-concept}"); a("\\end{table}")
    TABLES.mkdir(parents=True,exist_ok=True); TABLE_FILE.write_text("\n".join(L)+"\n")
    print(f"Wrote {TABLE_FILE}\n")
    print(f"{'concept':8s} {'stage':16s} {'ret':>4s} {'tp':>4s} {'gold':>4s} {'P':>5s} {'R':>5s} {'F1':>5s}")
    for concept,m,ret,tp,gold,P,R,F in console:
        print(f"{concept:8s} {m:16s} {ret:4d} {tp:4d} {gold:4d} {P:5.0f} {R:5.0f} {F:5.0f}")
    # error analysis dump
    print("\n=== Keyword false positives (concept present literally but judged NOT to apply) ===")
    for concept,cases in err_cases.items():
        print(f"-- {concept}: {len(cases)} false positives --")
        for rid,snip,reason in cases[:5]:
            s=snip[0] if snip else ""
            print(f"   r{rid}: {reason}  | {s[:90]}")
    (EVAL/"pr_concept_errors.json").write_text(json.dumps({c:[{'rid':r,'snip':s,'reason':rs} for r,s,rs in v] for c,v in err_cases.items()},indent=2))
    print(f"\nFull error cases -> {EVAL/'pr_concept_errors.json'}")

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("build")
    j=sub.add_parser("judge"); j.add_argument("--workers",type=int,default=8); j.add_argument("--overwrite",action="store_true")
    sub.add_parser("aggregate")
    args=p.parse_args()
    {"build":cmd_build,"judge":cmd_judge,"aggregate":cmd_aggregate}[args.cmd](args)

if __name__=="__main__":
    main()
