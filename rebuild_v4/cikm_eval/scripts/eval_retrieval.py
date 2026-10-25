"""
Retrieval-effectiveness evaluation (selling point #3: end-user benefit).

Question: subjective requests like "comfort food for sick kids" are hard to
satisfy with traditional search. Does SER let users find relevant recipes that
keyword search cannot?

Three systems compared on the same subjective queries:
  A. Catalog keyword  - BM25 over recipe name + description + ingredients
                        (what a normal recipe site has).
  B. Review keyword   - BM25 over the raw review text (naive use of UGC, no structure).
  C. SER (ours)       - match the query's facet values against the extracted +
                        normalized subjective attributes; rank by #facets matched.

Protocol (TREC-style pooling + LLM relevance judgments):
  - each system returns top-k recipes per query
  - we pool all retrieved (query, recipe) pairs and judge each for relevance with
    an independent LLM (gpt-oss). The judge sees ONLY neutral catalog info + a few
    review snippets, never our extracted attributes, so it does not favor SER.
  - metrics: Success@k (>=1 relevant in top-k), Precision@k, nDCG@k, and the
    intuitive zero-relevant rate (fraction of queries with NO relevant hit in top-k).

Grounding: nDCG (Jarvelin & Kekalainen, TOIS 2002); pooling (TREC, Voorhees);
LLM relevance judgments (Thomas et al., SIGIR 2024; LLMJudge / LLM4Eval 2024).
Note: LLM judges tend to over-credit query-term overlap (Alaofi et al. 2024),
which if anything inflates the keyword baselines -- a conservative bias for us.

Usage:
  python3 scripts/eval_retrieval.py build   --k 5
  python3 scripts/eval_retrieval.py judge   --workers 8
  python3 scripts/eval_retrieval.py aggregate --k 5
"""
from __future__ import annotations
import argparse, json, math, os, re, sys, threading, time
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT = Path("/Users/liliu/SER-DB")
PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TABLES = PAPER / "tables"
EXHIBIT = ROOT / "food-exhibit-data-500recipes.json"
GOLD = EVAL / "query_to_facet_gold.json"
POOL_FILE = EVAL / "retrieval_pool.jsonl"
JUDG_FILE = EVAL / "retrieval_judgments.jsonl"
TABLE_FILE = TABLES / "retrieval.tex"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")
REASONING_EFFORT = os.environ.get("JUDGE_REASONING_EFFORT", "low")

ATTR_FIELDS = ["taste_attributes","texture_attributes","meal_type_attributes",
               "occasion_attributes","audience_attributes","type_attributes"]
FACET_TO_FIELD = {
    "taste_flavor":"taste_attributes","texture_mouthfeel":"texture_attributes",
    "meal_type":"meal_type_attributes","occasion_holiday":"occasion_attributes",
    "audience_enjoyment":"audience_attributes","cuisine_type":"type_attributes",
}

TOKEN = re.compile(r"[a-z0-9]+")
def toks(s): return TOKEN.findall((s or "").lower())

def clean_html(s):
    return re.sub(r"&[a-z]+;|<[^>]+>", " ", s or "")


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = docs                      # list[list[str]]
        self.N = len(docs)
        self.k1, self.b = k1, b
        self.dl = [len(d) for d in docs]
        self.avgdl = sum(self.dl)/max(self.N,1)
        df = Counter()
        for d in docs:
            for t in set(d): df[t]+=1
        self.idf = {t: math.log(1+(self.N-n+0.5)/(n+0.5)) for t,n in df.items()}
        self.tf = [Counter(d) for d in docs]
    def score(self, q):
        q = toks(q) if isinstance(q,str) else q
        out = []
        for i in range(self.N):
            s=0.0; tf=self.tf[i]; dl=self.dl[i]
            for t in q:
                if t not in tf: continue
                idf=self.idf.get(t,0.0)
                num=tf[t]*(self.k1+1)
                den=tf[t]+self.k1*(1-self.b+self.b*dl/self.avgdl)
                s+=idf*num/den
            out.append(s)
        return out
    def topk(self, q, k):
        sc=self.score(q)
        idx=sorted(range(self.N), key=lambda i:-sc[i])
        return [(i,sc[i]) for i in idx[:k] if sc[i]>0]


def load_recipes():
    data=json.load(open(EXHIBIT))["items"]
    catalog_docs=[]; review_docs=[]; meta=[]
    for it in data:
        name=it.get("name","") or it.get("label","")
        desc=clean_html(it.get("description",""))
        ingr=" ".join(it.get("ingredients",[]) or [])
        catalog_docs.append(toks(f"{name} {desc} {ingr}"))
        rv=" ".join(clean_html(r.get("review_text","")) for r in (it.get("reviews") or []))
        review_docs.append(toks(rv))
        meta.append(it)
    return data, catalog_docs, review_docs, meta


def ser_retrieve(item_facets_map, query_gold, k):
    """SER: rank recipes by number of distinct query facet-values matched."""
    scores=[]
    for i, attrs in enumerate(item_facets_map):
        matched=0; total_support=0
        for fac, vals in query_gold.items():
            field=FACET_TO_FIELD.get(fac)
            if not field: continue
            have=attrs.get(field,set())
            for v in vals:
                if v.lower() in have:
                    matched+=1; total_support+=1
        if matched>0:
            scores.append((i, matched + 0.001*total_support))
    scores.sort(key=lambda x:-x[1])
    return scores[:k]


def cmd_build(args):
    data, catalog_docs, review_docs, meta = load_recipes()
    bm_cat=BM25(catalog_docs); bm_rev=BM25(review_docs)
    # precompute per-recipe attribute sets
    item_facets=[]
    for it in data:
        d={f:set(x.lower() for x in (it.get(f,[]) or [])) for f in ATTR_FIELDS}
        item_facets.append(d)
    gold=json.load(open(GOLD))["queries"]

    pairs={}   # (qid, recipe_idx) -> dict
    runs=defaultdict(lambda: defaultdict(list))  # system -> qid -> [recipe_idx ranked]
    for q in gold:
        qid=q["id"]; qtext=q["text"]; qgold=q["gold"]
        A=bm_cat.topk(qtext, args.k)
        B=bm_rev.topk(qtext, args.k)
        C=ser_retrieve(item_facets, qgold, args.k)
        for sysname, res in [("catalog",A),("review",B),("ser",C)]:
            for rank,(idx,sc) in enumerate(res):
                runs[sysname][qid].append(idx)
                key=(qid,idx)
                if key not in pairs:
                    it=data[idx]
                    snippets=[clean_html(r.get("review_text",""))[:300] for r in (it.get("reviews") or [])[:3]]
                    pairs[key]={
                        "qid":qid,"query":qtext,"recipe_idx":idx,
                        "recipe_name":it.get("name") or it.get("label"),
                        "description":clean_html(it.get("description",""))[:400],
                        "ingredients":it.get("ingredients",[])[:12],
                        "review_snippets":snippets,
                    }
    EVAL.mkdir(parents=True,exist_ok=True)
    with open(POOL_FILE,"w") as f:
        for key,v in pairs.items():
            f.write(json.dumps(v)+"\n")
    (EVAL/"retrieval_runs.json").write_text(json.dumps(
        {s:{q:idxs for q,idxs in qd.items()} for s,qd in runs.items()}, indent=2))
    print(f"Queries: {len(gold)}  |  pooled (query,recipe) pairs to judge: {len(pairs)}")
    for s in ("catalog","review","ser"):
        nonempty=sum(1 for q in runs[s] if runs[s][q])
        print(f"  {s:8s}: returned >=1 result for {nonempty}/{len(gold)} queries")
    print(f"Wrote {POOL_FILE} and retrieval_runs.json")


JUDGE_SYS = """You judge whether a recipe is RELEVANT to a user's subjective search request.
You are given the request, the recipe name, its description, ingredients, and a few real review snippets.
Decide if a user issuing this request would find this recipe a relevant, satisfying result.
Be strict: surface plausibility is not enough; the recipe should genuinely fit the request's intent.
Return STRICT JSON only: {"relevant": true|false, "reason": "<one short sentence>"}"""

def make_rel_prompt(p):
    rs="\n".join(f"  - {s}" for s in p["review_snippets"])
    return (f"Request: {p['query']!r}\n\n"
            f"Recipe: {p['recipe_name']}\n"
            f"Description: {p['description']}\n"
            f"Ingredients: {', '.join(p['ingredients'])}\n"
            f"Review snippets:\n{rs}\n\nOutput JSON only.")

def call_judge(user, retries=3):
    url=API_BASE.rstrip('/')+"/chat/completions"
    payload={"model":JUDGE_MODEL,"messages":[{"role":"system","content":JUDGE_SYS},{"role":"user","content":user}],
             "temperature":0.0,"max_tokens":500,"reasoning_effort":REASONING_EFFORT}
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
            r=json.loads(l); done.add((r["qid"],r["recipe_idx"]))
        mode="a"
    else: mode="w"
    pend=[p for p in pairs if (p["qid"],p["recipe_idx"]) not in done]
    print(f"Judging {len(pend)} pairs (workers={args.workers})",flush=True)
    lock=threading.Lock(); c={"n":len(done)}; tot=len(pairs)
    def task(p): return p, call_judge(make_rel_prompt(p))
    with open(JUDG_FILE,mode) as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task,p) for p in pend]):
            p,j=fut.result()
            with lock:
                rec={**{k:p[k] for k in ("qid","query","recipe_idx","recipe_name")},"judgment":j}
                f.write(json.dumps(rec)+"\n"); f.flush(); c["n"]+=1
                rel=j.get("relevant") if "error" not in j else "ERR"
                print(f"  [{c['n']}/{tot}] {p['qid']} {str(rel):5s} {p['recipe_name'][:40]}",flush=True)

def cmd_aggregate(args):
    rel={}
    for l in open(JUDG_FILE):
        r=json.loads(l); j=r["judgment"]
        if "error" in j: continue
        rel[(r["qid"],r["recipe_idx"])]=bool(j.get("relevant"))
    runs=json.loads((EVAL/"retrieval_runs.json").read_text())
    gold=json.load(open(GOLD))["queries"]; qids=[q["id"] for q in gold]
    k=args.k

    def dcg(rels):
        return sum((1.0 if r else 0.0)/math.log2(i+2) for i,r in enumerate(rels))
    def metrics(system):
        succ=p_at=ndcg=zero=0; nq=len(qids)
        for qid in qids:
            ranked=runs[system].get(qid,[])[:k]
            rels=[rel.get((qid,idx),False) for idx in ranked]
            nrel=sum(rels)
            succ += 1 if nrel>0 else 0
            zero += 1 if nrel==0 else 0
            p_at += nrel/k
            ideal=dcg(sorted(rels,reverse=True))
            ndcg += (dcg(rels)/ideal) if ideal>0 else 0.0
        return dict(success=100*succ/nq, p_at=100*p_at/nq, ndcg=100*ndcg/nq, zero=100*zero/nq, nq=nq)

    names={"catalog":"A. Catalog keyword","review":"B. Review keyword","ser":"C. SER (ours)"}
    M={s:metrics(s) for s in ("catalog","review","ser")}
    L=[]; a=L.append
    a("% Auto-generated by scripts/eval_retrieval.py")
    a("\\begin{table}[t]"); a("\\centering"); a("\\small"); a("\\setlength{\\tabcolsep}{5pt}")
    a("\\begin{tabular}{@{}lrrrr@{}}")
    a("\\toprule")
    a(f"\\textbf{{System}} & \\textbf{{Success@{k}}} & \\textbf{{P@{k}}} & \\textbf{{nDCG@{k}}} & \\textbf{{Zero-rel}} \\\\")
    a(" & \\textbf{\\%} & \\textbf{\\%} & \\textbf{\\%} & \\textbf{\\%} \\\\")
    a("\\midrule")
    for s in ("catalog","review","ser"):
        m=M[s]; bold = (s=="ser")
        row=f"{names[s]} & {m['success']:.0f} & {m['p_at']:.0f} & {m['ndcg']:.0f} & {m['zero']:.0f}"
        a((f"\\textbf{{{row}}}" if bold else row)+" \\\\")
    a("\\bottomrule"); a("\\end{tabular}")
    a(f"\\caption{{Retrieval effectiveness on $n={len(qids)}$ subjective queries, top-{k}. "
      "Relevance pooled across systems and judged by an independent LLM (gpt-oss) that sees only "
      "neutral catalog text and review snippets, never SER's extracted attributes. "
      "\\emph{Success@k}: a relevant recipe appears in the top $k$; \\emph{Zero-rel}: queries with no "
      "relevant hit in top $k$ (lower is better). Metrics: nDCG~\\cite{jarvelin2002cumulated}; "
      "LLM relevance judging follows~\\cite{thomas2024large}.}}")
    a("\\label{tab:retrieval}"); a("\\end{table}")
    TABLES.mkdir(parents=True,exist_ok=True); TABLE_FILE.write_text("\n".join(L)+"\n")
    print(f"Wrote {TABLE_FILE}\n")
    print(f"{'System':20s} {'Succ@k':>7s} {'P@k':>6s} {'nDCG':>6s} {'Zero-rel':>9s}")
    for s in ("catalog","review","ser"):
        m=M[s]; print(f"  {names[s]:18s} {m['success']:6.0f}% {m['p_at']:5.0f}% {m['ndcg']:5.0f}% {m['zero']:8.0f}%")
    print(f"\n(n={len(qids)} queries, k={k})")

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build"); b.add_argument("--k",type=int,default=5)
    j=sub.add_parser("judge"); j.add_argument("--workers",type=int,default=8); j.add_argument("--overwrite",action="store_true")
    g=sub.add_parser("aggregate"); g.add_argument("--k",type=int,default=5)
    args=p.parse_args()
    {"build":cmd_build,"judge":cmd_judge,"aggregate":cmd_aggregate}[args.cmd](args)

if __name__=="__main__":
    main()
