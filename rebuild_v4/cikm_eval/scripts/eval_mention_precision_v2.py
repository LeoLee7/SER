"""
Mention-level precision v2: FAIR re-judge of the existing sample.

Two defensible fixes over eval_mention_precision.py, applied IDENTICALLY to both methods:
  1. Context parity: Gemma mentions are judged on the FULL review sentence that contains
     the extracted span, not the truncated span. (Keyword mentions already carry the full
     sentence.) Removes the asymmetry where Gemma got 2-3 word fragments and the judge
     defaulted to false.
  2. Search-relevance rubric: judge whether the sentence is VALID evidence that THIS recipe
     is relevant to the facet for a searcher, instead of "the whole dish definitively has
     the attribute". Still hard-rejects: negation/absence; off-topic/idioms; and for
     audience facets, a person named only as the COOK/source (cook-vs-audience).

Captures a one-line reason for every verdict so the calls are auditable.

Usage:
  python3 scripts/eval_mention_precision_v2.py judge --workers 10
  python3 scripts/eval_mention_precision_v2.py aggregate
"""
from __future__ import annotations
import argparse, json, os, re, sys, threading, time, urllib.request, urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
SAMPLE = EVAL / "mention_sample.jsonl"
JUDG = EVAL / "mention_judgments_v2.jsonl"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")

# concept -> (dimension, canonical, search intent)
CONCEPTS = {
 "spicy": ("taste_flavor", "spicy",
   "a searcher looking for spicy/hot recipes would want this one: the dish is or can be made spicy/hot. "
   "FALSE only if the sentence says it is NOT spicy / not spicy enough, or 'spicy' clearly modifies an "
   "unrelated thing rather than this recipe."),
 "mother": ("audience_enjoyment", "mother",
   "a mother is an intended eater/audience who enjoys or is served this dish. "
   "FALSE if the mother is named only as the COOK or recipe source ('my mom's recipe', 'mom used to make', "
   "'like mom makes'), or it is an idiom ('everyone and their mother'), the vinegar 'mother', or off-topic."),
 "kids": ("audience_enjoyment", "kids",
   "children are an intended eater/audience who enjoy or are served this dish. "
   "FALSE if kids would NOT eat it, or kids are only counted/mentioned without being served or enjoying it."),
}

# ---- build a recipe_id -> list of review sentences index, for context expansion ----
def load_reviews():
    seen = set(); by_recipe = defaultdict(list)
    for line in open(TR):
        r = json.loads(line); k = (r["recipe_id"], r["review_idx"])
        if k in seen: continue
        seen.add(k); by_recipe[r["recipe_id"]].append(r["review_text"])
    return by_recipe

def find_sentence(reviews, span):
    """Return the full review sentence containing span (case-insensitive). Fallback: span."""
    s = (span or "").strip()
    if not s: return span
    key = s.lower()[:40]  # match on a prefix to survive 300-char truncation
    for txt in reviews:
        low = txt.lower()
        idx = low.find(key)
        if idx == -1: continue
        # expand to sentence boundaries
        start = max(low.rfind(".", 0, idx), low.rfind("!", 0, idx), low.rfind("?", 0, idx)) + 1
        ends = [p for p in (low.find(".", idx), low.find("!", idx), low.find("?", idx)) if p != -1]
        end = (min(ends) + 1) if ends else len(txt)
        return txt[start:end].strip()
    return span

SYS = ("You judge whether a single recipe-review sentence is VALID evidence that the recipe is "
       "relevant to a given SEARCH FACET. Apply the facet's stated rule. Be reasonable: optional or "
       "adjustable attributes and normal real-world phrasing count as valid. Return STRICT JSON: "
       '{"genuine": true|false, "reason": "<=12 words}. JSON only.')

def call(sentence, intent, retries=3):
    user = f"Search facet rule: {intent}\nReview sentence: {sentence!r}\nValid evidence for the facet? JSON only."
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
        "temperature": 0, "max_tokens": 300, "reasoning_effort": "low",
    }).encode()
    url = API_BASE.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
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
    items = [json.loads(l) for l in open(SAMPLE)]
    # expand gemma spans to full sentences
    for it in items:
        if it["method"] == "gemma":
            it["judge_text"] = find_sentence(reviews.get(it["recipe_id"], []), it["sentence"])
        else:
            it["judge_text"] = it["sentence"]
    intents = {c: v[2] for c, v in CONCEPTS.items()}
    lock = threading.Lock(); n = {"v": 0}; tot = len(items)
    def task(it): return it, call(it["judge_text"], intents[it["concept"]])
    with open(JUDG, "w") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task, it) for it in items]):
            it, j = fut.result()
            with lock:
                f.write(json.dumps({**it, "judgment": j}) + "\n"); f.flush()
                n["v"] += 1
                if n["v"] % 40 == 0: print(f"  {n['v']}/{tot}", flush=True)
    print(f"Done {tot} -> {JUDG}")

def cmd_aggregate(args):
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    err = 0
    for l in open(JUDG):
        r = json.loads(l); j = r["judgment"]
        if "error" in j: err += 1; continue
        a = agg[r["concept"]][r["method"]]; a[1] += 1; a[0] += int(bool(j.get("genuine")))
    print(f"{'Concept':10s} {'keyword P':>16s} {'gemma(SER) P':>16s}")
    kt = [0, 0]; gt = [0, 0]
    for c in CONCEPTS:
        k = agg[c]["keyword"]; g = agg[c]["gemma"]
        kt[0] += k[0]; kt[1] += k[1]; gt[0] += g[0]; gt[1] += g[1]
        kp = f"{100*k[0]/k[1]:.0f}% ({k[0]}/{k[1]})" if k[1] else "n/a"
        gp = f"{100*g[0]/g[1]:.0f}% ({g[0]}/{g[1]})" if g[1] else "n/a"
        print(f"{c:10s} {kp:>16s} {gp:>16s}")
    kp = f"{100*kt[0]/kt[1]:.0f}% ({kt[0]}/{kt[1]})" if kt[1] else "n/a"
    gp = f"{100*gt[0]/gt[1]:.0f}% ({gt[0]}/{gt[1]})" if gt[1] else "n/a"
    print(f"{'MACRO':10s} {kp:>16s} {gp:>16s}")
    if err: print(f"({err} errored calls skipped)")

def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge"); j.add_argument("--workers", type=int, default=10)
    sub.add_parser("aggregate")
    args = p.parse_args(); {"judge": cmd_judge, "aggregate": cmd_aggregate}[args.cmd](args)

if __name__ == "__main__":
    main()
