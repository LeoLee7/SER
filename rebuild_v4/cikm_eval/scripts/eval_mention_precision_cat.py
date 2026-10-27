"""
Mention-level precision, multi-concept, keyword vs SER (Gemma) extraction.
Same fair protocol as eval_mention_precision_v2.py:
  - judge the FULL review sentence for BOTH methods (context parity),
  - search-relevance rubric, hard-rejecting negation / off-topic / wrong-referent,
  - capture a one-line reason per verdict.
Builds a fresh sample per concept (n per method) and judges via gpt-oss (cross-family).

Usage:
  python3 scripts/eval_mention_precision_multi.py run --n 40 --workers 12
  python3 scripts/eval_mention_precision_multi.py aggregate
"""
from __future__ import annotations
import argparse, json, os, re, sys, threading, time, random, urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
PR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl")
SAMPLE = EVAL / "mention_cat_sample.jsonl"
JUDG = EVAL / "mention_cat_judgments.jsonl"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")

# concept -> (dimension, canonical word, search-relevance intent w/ hard-reject clause)
CONCEPTS = {
 "christmas": ("occasion_holiday","christmas","the dish is served at or intended for Christmas. FALSE if 'christmas' is off-topic (a gift, a place/person name) or negated."),
 "thanksgiving": ("occasion_holiday","thanksgiving","the dish is served at or intended for Thanksgiving. FALSE if off-topic or negated."),
 "birthday": ("occasion_holiday","birthday","the dish is served at or for a birthday. FALSE if 'birthday' is unrelated to the dish or negated."),
 "potluck": ("occasion_holiday","potluck","the dish is suitable for or brought to a potluck. FALSE if negated or off-topic."),
 "party": ("occasion_holiday","party","the dish is served at or suitable for a party. FALSE if 'party' means group size ('party of four') or is off-topic."),
 "italian": ("cuisine_type","italian","the dish is Italian in cuisine/style. FALSE if 'italian' only names a single ingredient (Italian seasoning/dressing) in an otherwise non-Italian dish, or is off-topic."),
 "mexican": ("cuisine_type","mexican","the dish is Mexican in cuisine/style. FALSE if 'mexican' only names an ingredient (Mexican cheese blend) in a non-Mexican dish, or is off-topic."),
 "chinese": ("cuisine_type","chinese","the dish is Chinese in cuisine/style. FALSE if off-topic (e.g. a takeout comparison) or negated."),
 "southern": ("cuisine_type","southern","the dish is Southern (US) in cuisine/style. FALSE if 'southern' refers to a region unrelated to the food's style, or is off-topic."),
}

def sentences(text, word):
    pat = re.compile(r"[^.!?]*\b" + re.escape(word) + r"\b[^.!?]*[.!?]?", re.I)
    return [m.group().strip() for m in pat.finditer(text)]

def load_reviews():
    seen = set(); by_recipe = defaultdict(list); flat = []
    for line in open(TR):
        r = json.loads(line); k = (r["recipe_id"], r["review_idx"])
        if k in seen: continue
        seen.add(k); by_recipe[r["recipe_id"]].append(r["review_text"]); flat.append((r["recipe_id"], r["review_text"]))
    return by_recipe, flat

def find_sentence(reviews, span):
    s = (span or "").strip()
    if not s: return span
    key = s.lower()[:40]
    for txt in reviews:
        low = txt.lower(); idx = low.find(key)
        if idx == -1: continue
        start = max(low.rfind(".", 0, idx), low.rfind("!", 0, idx), low.rfind("?", 0, idx)) + 1
        ends = [p for p in (low.find(".", idx), low.find("!", idx), low.find("?", idx)) if p != -1]
        end = (min(ends) + 1) if ends else len(txt)
        return txt[start:end].strip()
    return span

def cmd_run(args):
    if not API_KEY or API_KEY == "EMPTY": sys.exit("Set NRP_API_KEY")
    rng = random.Random(7)
    by_recipe, flat = load_reviews()
    # gemma source_texts per concept (entity == canonical)
    gemma_src = defaultdict(list)
    for line in open(PR):
        r = json.loads(line)
        for a in r["attributes"]:
            for c, (dim, w, _) in CONCEPTS.items():
                if a["dimension"] == dim and (a.get("entity") or "").strip().lower() == c:
                    st = (a.get("source_text") or "").strip()
                    if st: gemma_src[c].append((r["recipe_id"], st))
    items = []
    for c, (dim, w, intent) in CONCEPTS.items():
        km = [(rid, s) for rid, txt in flat for s in sentences(txt, w)]
        km = rng.sample(km, min(args.n, len(km)))
        for rid, s in km:
            items.append({"concept": c, "method": "keyword", "recipe_id": rid, "judge_text": s[:300]})
        gm = rng.sample(gemma_src[c], min(args.n, len(gemma_src[c])))
        for rid, st in gm:
            items.append({"concept": c, "method": "gemma", "recipe_id": rid,
                          "span": st[:120], "judge_text": find_sentence(by_recipe.get(rid, []), st)[:300]})
        print(f"  {c}: keyword {len(km)}, gemma {len(gm)}", flush=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE, "w") as f:
        for it in items: f.write(json.dumps(it) + "\n")
    # judge
    intents = {c: v[2] for c, v in CONCEPTS.items()}
    lock = threading.Lock(); n = {"v": 0}; tot = len(items)
    def task(it): return it, call(it["judge_text"], intents[it["concept"]])
    with open(JUDG, "w") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(task, it) for it in items]):
            it, j = fut.result()
            with lock:
                f.write(json.dumps({**it, "judgment": j}) + "\n"); f.flush()
                n["v"] += 1
                if n["v"] % 40 == 0: print(f"  judged {n['v']}/{tot}", flush=True)
    print(f"Done {tot} -> {JUDG}")

SYS = ("You judge whether a single recipe-review sentence is VALID evidence that the recipe is "
       "relevant to a given SEARCH FACET. Apply the facet's stated rule, including its FALSE clause. "
       "Be reasonable: normal real-world phrasing counts. Return STRICT JSON: "
       '{"genuine": true|false, "reason": "<=12 words}. JSON only.')

def call(sentence, intent, retries=3):
    user = f"Search facet rule: {intent}\nReview sentence: {sentence!r}\nValid evidence for the facet? JSON only."
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

def cmd_aggregate(args):
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for l in open(JUDG):
        r = json.loads(l); j = r["judgment"]
        if "error" in j: continue
        a = agg[r["concept"]][r["method"]]; a[1] += 1; a[0] += int(bool(j.get("genuine")))
    print(f"{'Concept':10s} {'keyword':>14s} {'SER(gemma)':>14s} {'delta':>7s}")
    rows = []
    for c in CONCEPTS:
        k = agg[c]["keyword"]; g = agg[c]["gemma"]
        if not k[1] or not g[1]: continue
        kp = 100*k[0]/k[1]; gp = 100*g[0]/g[1]
        rows.append((c, kp, gp, gp-kp))
        print(f"{c:10s} {kp:>6.0f}% ({k[0]}/{k[1]}) {gp:>6.0f}% ({g[0]}/{g[1]}) {gp-kp:>+6.0f}")
    print("--- sorted by SER win ---")
    for c, kp, gp, d in sorted(rows, key=lambda x: -x[3]):
        print(f"  {c:10s} keyword {kp:.0f}%  SER {gp:.0f}%  (+{d:.0f})")

def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--n", type=int, default=40); r.add_argument("--workers", type=int, default=12)
    sub.add_parser("aggregate")
    args = p.parse_args(); {"run": cmd_run, "aggregate": cmd_aggregate}[args.cmd](args)

if __name__ == "__main__":
    main()
