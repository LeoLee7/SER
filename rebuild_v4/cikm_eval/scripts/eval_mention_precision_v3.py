"""
Mention-level precision v3: coreference-aware re-judge for the per-facet fused table.

Same fair protocol as v2/multi, plus one fix: the judge is given the FULL REVIEW as context
and asked to resolve pronouns/abbreviations (DH, hubby, "he") before ruling on the quoted
mention. This removes the sentence-level coreference artifact that under-counted person facets
(husband). Applied IDENTICALLY to keyword and gemma, for the perfacet concepts so the fused
table's rows share one methodology.

Reuses the already-built sample (mention_multi_sample.jsonl).

Usage:
  python3 scripts/eval_mention_precision_v3.py judge --workers 12
  python3 scripts/eval_mention_precision_v3.py aggregate
"""
from __future__ import annotations
import argparse, json, os, sys, threading, time, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
SAMPLE = EVAL / "mention_multi_sample.jsonl"
JUDG = EVAL / "mention_v3_judgments.jsonl"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")

CONCEPTS = ["husband", "kids", "tangy", "spicy"]
INTENT = {
 "husband": "a husband enjoys or is served this dish. Resolve DH/hubby/hubs/hubbie/'he' to the husband. FALSE if the husband dislikes/will not eat it, or 'husband' appears only as the cook, shopper, or bystander with no sign he eats it.",
 "kids":    "children enjoy or are served this dish. FALSE if kids would NOT eat it, or kids are only counted/listed without eating it.",
 "tangy":   "the dish has a tangy/tart flavor. FALSE if negated or 'tangy' modifies an unrelated thing (a sauce brand, another recipe).",
 "spicy":   "the dish is or can be made spicy/hot. FALSE if it says NOT spicy / not spicy enough, or 'spicy' modifies an unrelated thing.",
}

def load_reviews():
    seen = set(); by_recipe = defaultdict(list)
    for line in open(TR):
        r = json.loads(line); k = (r["recipe_id"], r["review_idx"])
        if k in seen: continue
        seen.add(k); by_recipe[r["recipe_id"]].append(r["review_text"])
    return by_recipe

def full_review(reviews, snippet):
    key = (snippet or "").strip().lower()[:40]
    for txt in reviews:
        if key and key in txt.lower(): return txt
    return snippet

SYS = ("You judge whether a quoted mention from a recipe review is VALID evidence that the recipe "
       "is relevant to a SEARCH FACET. Use the full review only to resolve pronouns/abbreviations and "
       "context; base the verdict on the quoted mention and the facet rule (including its FALSE clause). "
       'Return STRICT JSON: {"genuine": true|false, "reason": "<=12 words}. JSON only.')

def call(review, mention, intent, retries=3):
    user = (f"Full review (context only): {review[:900]!r}\nFacet rule: {intent}\n"
            f"Quoted mention to judge: {mention!r}\nValid evidence for the facet? JSON only.")
    payload = json.dumps({"model": MODEL, "messages": [
        {"role": "system", "content": SYS}, {"role": "user", "content": user}],
        "temperature": 0, "max_tokens": 300, "reasoning_effort": "low"}).encode()
    req = urllib.request.Request(API_BASE.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                t = json.loads(resp.read())["choices"][0]["message"].get("content", "").strip()
            if t.startswith("```"):
                t = t.strip("`"); t = t[4:].strip() if t.lower().startswith("json") else t
            return json.loads(t)
        except Exception as e:
            if a == retries - 1: return {"error": str(e)}
            time.sleep(2 ** a)

def cmd_judge(args):
    if not API_KEY or API_KEY == "EMPTY": sys.exit("Set NRP_API_KEY")
    reviews = load_reviews()
    items = [json.loads(l) for l in open(SAMPLE) if json.loads(l)["concept"] in CONCEPTS]
    lock = threading.Lock(); n = {"v": 0}; tot = len(items)
    def task(it):
        rv = full_review(reviews.get(it["recipe_id"], []), it["judge_text"])
        return it, call(rv, it["judge_text"], INTENT[it["concept"]])
    with open(JUDG, "w") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task, it) for it in items]):
            it, j = fut.result()
            with lock:
                f.write(json.dumps({**it, "judgment": j}) + "\n"); f.flush()
                n["v"] += 1
                if n["v"] % 40 == 0: print(f"  judged {n['v']}/{tot}", flush=True)
    print(f"Done {tot} -> {JUDG}")

def cmd_aggregate(args):
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for l in open(JUDG):
        r = json.loads(l); j = r["judgment"]
        if "error" in j: continue
        a = agg[r["concept"]][r["method"]]; a[1] += 1; a[0] += int(bool(j.get("genuine")))
    print(f"{'Concept':10s} {'keyword':>14s} {'SER(gemma)':>14s} {'delta':>7s}")
    for c in CONCEPTS:
        k = agg[c]["keyword"]; g = agg[c]["gemma"]
        if not k[1] or not g[1]: continue
        kp = 100*k[0]/k[1]; gp = 100*g[0]/g[1]
        print(f"{c:10s} {kp:>6.0f}% ({k[0]}/{k[1]}) {gp:>6.0f}% ({g[0]}/{g[1]}) {gp-kp:>+6.0f}")

def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge"); j.add_argument("--workers", type=int, default=12)
    sub.add_parser("aggregate")
    args = p.parse_args(); {"judge": cmd_judge, "aggregate": cmd_aggregate}[args.cmd](args)

if __name__ == "__main__":
    main()
