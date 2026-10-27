"""
Mention-level precision: keyword matching vs Gemma extraction.

Recipe-level precision washes out negation (a recipe has many reviews). The negation /
irrelevant problem is a MENTION-level phenomenon, so we measure it there.

For a concept c with canonical word w:
  - keyword mentions = review sentences that literally contain w (what a substring search
    would surface as evidence). Judge each: does the dish genuinely have attribute c?
  - gemma mentions   = the source_text sentences Gemma actually extracted as c. Judge same.
keyword mention precision is low (negations / off-topic / ingredient slip in); Gemma
mention precision is high because it reads context and does not extract from negations.

Judge: gpt-oss (independent, cross-family). Sample N sentences per (concept, method).

Usage:
  python3 scripts/eval_mention_precision.py build --n 40
  python3 scripts/eval_mention_precision.py judge --workers 10
  python3 scripts/eval_mention_precision.py aggregate
"""
from __future__ import annotations
import argparse, json, os, re, sys, threading, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
PR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl")
SAMPLE = EVAL / "mention_sample.jsonl"
JUDG = EVAL / "mention_judgments.jsonl"

API_BASE=os.environ.get("NRP_API_BASE","https://ellm.nrp-nautilus.io/v1")
API_KEY=os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
MODEL=os.environ.get("JUDGE_MODEL","gpt-oss")

# concept -> (dimension, canonical word for keyword, intent for judge)
CONCEPTS={
 "spicy":("taste_flavor","spicy","the dish is genuinely spicy/hot in flavor (NOT 'not spicy', NOT a wish for more spice, NOT 'spicy mustard' used merely as an added condiment)"),
 "mother":("audience_enjoyment","mother","a mother genuinely enjoys or would enjoy the dish (NOT a past memory like 'my mother used to make it', NOT gifting, NOT an off-topic mention)"),
 "kids":("audience_enjoyment","kids","children genuinely enjoy the dish (NOT 'kids wouldn't touch it', NOT merely mentioned without enjoyment)"),
}

def sentences(text, word):
    # sentences containing the whole word (case-insensitive)
    pat=re.compile(r"[^.!?]*\b"+re.escape(word)+r"\b[^.!?]*[.!?]?", re.I)
    return [m.group().strip() for m in pat.finditer(text)]

def cmd_build(args):
    import random
    rng=random.Random(7)
    # review text per recipe-review
    seen=set(); reviews=[]
    for line in open(TR):
        r=json.loads(line); k=(r["recipe_id"],r["review_idx"])
        if k in seen: continue
        seen.add(k); reviews.append((r["recipe_id"],r["review_text"]))
    # gemma source_texts per concept
    gemma_src=defaultdict(list)
    for line in open(PR):
        r=json.loads(line)
        for a in r["attributes"]:
            for c,(dim,w,_) in CONCEPTS.items():
                if a["dimension"]==dim and (a.get("entity") or "").strip().lower()==c:
                    st=(a.get("source_text") or "").strip()
                    if st: gemma_src[c].append((r["recipe_id"],st))
    out=[]
    for c,(dim,w,intent) in CONCEPTS.items():
        # keyword mentions
        km=[]
        for rid,txt in reviews:
            for s in sentences(txt,w):
                km.append((rid,s))
        km=rng.sample(km, min(args.n,len(km)))
        for rid,s in km: out.append({"concept":c,"method":"keyword","recipe_id":rid,"sentence":s[:300]})
        # gemma mentions
        gm=rng.sample(gemma_src[c], min(args.n,len(gemma_src[c])))
        for rid,s in gm: out.append({"concept":c,"method":"gemma","recipe_id":rid,"sentence":s[:300]})
        print(f"  {c}: keyword {len(km)} mentions, gemma {len(gm)} mentions")
    EVAL.mkdir(parents=True,exist_ok=True)
    with open(SAMPLE,"w") as f:
        for o in out: f.write(json.dumps(o)+"\n")
    print(f"Wrote {SAMPLE} ({len(out)} sentences)")

SYS="""You judge a single sentence from a recipe review. Decide if it indicates the DISH
genuinely has the stated attribute. Answer "no" for negations, wishes, off-topic uses, or
ingredient-only mentions. Return STRICT JSON: {"genuine": true|false}. JSON only."""

def call(sent,intent,retries=3):
    user=f"Attribute: {intent}\nSentence: {sent!r}\nDoes the dish genuinely have this attribute? JSON only."
    url=API_BASE.rstrip('/')+"/chat/completions"
    payload={"model":MODEL,"messages":[{"role":"system","content":SYS},{"role":"user","content":user}],"temperature":0,"max_tokens":200,"reasoning_effort":"low"}
    h={"Content-Type":"application/json","Authorization":f"Bearer {API_KEY}"}
    t=None
    for a in range(retries):
        try:
            r=requests.post(url,headers=h,json=payload,timeout=120); r.raise_for_status()
            t=(r.json()["choices"][0]["message"].get("content") or "").strip()
            if t.startswith("```"): t=t.strip("`"); t=t[4:].strip() if t.lower().startswith("json") else t
            return json.loads(t)
        except Exception as e:
            if a==retries-1: return {"error":str(e)}
            time.sleep(2**a)

def cmd_judge(args):
    if not API_KEY or API_KEY=="EMPTY": sys.exit("Set NRP_API_KEY")
    items=[json.loads(l) for l in open(SAMPLE)]
    done=set()
    if JUDG.exists() and not args.overwrite:
        for l in open(JUDG):
            r=json.loads(l); done.add((r["concept"],r["method"],r["recipe_id"],r["sentence"][:40]))
        mode="a"
    else: mode="w"
    intents={c:v[2] for c,v in CONCEPTS.items()}
    pend=[it for it in items if (it["concept"],it["method"],it["recipe_id"],it["sentence"][:40]) not in done]
    print(f"Judging {len(pend)} (workers={args.workers})",flush=True)
    lock=threading.Lock(); cnt={"n":len(done)}; tot=len(items)
    def task(it): return it, call(it["sentence"], intents[it["concept"]])
    with open(JUDG,mode) as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task,it) for it in pend]):
            it,j=fut.result()
            with lock:
                f.write(json.dumps({**it,"judgment":j})+"\n"); f.flush(); cnt["n"]+=1
                if cnt["n"]%40==0: print(f"  {cnt['n']}/{tot}",flush=True)

def cmd_aggregate(args):
    agg=defaultdict(lambda:defaultdict(lambda:[0,0]))  # concept->method->[genuine,total]
    for l in open(JUDG):
        r=json.loads(l); j=r["judgment"]
        if "error" in j: continue
        a=agg[r["concept"]][r["method"]]; a[1]+=1; a[0]+=int(bool(j.get("genuine")))
    print(f"{'Concept':10s} {'keyword mention P':>18s} {'gemma mention P':>16s}")
    for c in CONCEPTS:
        k=agg[c]["keyword"]; g=agg[c]["gemma"]
        kp=f"{100*k[0]/k[1]:.0f}% ({k[0]}/{k[1]})" if k[1] else "n/a"
        gp=f"{100*g[0]/g[1]:.0f}% ({g[0]}/{g[1]})" if g[1] else "n/a"
        print(f"{c:10s} {kp:>18s} {gp:>16s}")

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build"); b.add_argument("--n",type=int,default=40)
    j=sub.add_parser("judge"); j.add_argument("--workers",type=int,default=10); j.add_argument("--overwrite",action="store_true")
    sub.add_parser("aggregate")
    args=p.parse_args(); {"build":cmd_build,"judge":cmd_judge,"aggregate":cmd_aggregate}[args.cmd](args)

if __name__=="__main__": main()
