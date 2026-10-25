"""
Run ONE round of the agentic normalization skill on the raw Gemma extraction,
to produce a v1 snapshot (one-round merge + blacklist). The deployed demo is the
converged result and serves as v2. Comparing v1 to v2 shows the value of iterating
the agentic loop.

One round = for each category, show the LLM (gpt-oss) the most frequent raw extracted
values and ask it, in a single pass, to (a) blacklist non-discriminative noise and
(b) group obvious synonyms variant -> canonical. We apply only this single-pass output
to get v1. We deliberately do NOT iterate; that is what makes it "round 1".

Output: eval_data/round1_v1.json  = {dim: {blacklist:[...], merges:{canonical:[variants]}}}
"""
from __future__ import annotations
import json, os, sys, time
from collections import Counter, defaultdict
from pathlib import Path
import requests

PAPER = Path(__file__).resolve().parents[1]
EVAL = PAPER / "eval_data"
TR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
OUT = EVAL / "round1_v1.json"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")

DIMS = ["taste_flavor","texture_mouthfeel","meal_type","occasion_holiday","audience_enjoyment","cuisine_type"]
INTENT = {
    "taste_flavor":"taste/flavor of the dish (sweet, tangy, savory, spicy). Generic praise (delicious, good, amazing) is noise.",
    "texture_mouthfeel":"physical mouthfeel (tender, crispy, moist, creamy). Generic words (good, nice, texture) are noise.",
    "meal_type":"meal/dish role (breakfast, dinner, dessert, side-dish). Generic words (food, dish, meal) are noise.",
    "occasion_holiday":"a specific occasion/holiday (Christmas, birthday, potluck, weeknight). Meal times and generic words are noise.",
    "audience_enjoyment":"WHO ENJOYED eating it (kids, husband, family, guests). First-person/cook references (I, we, me, self) and generic (everyone, people) are noise.",
    "cuisine_type":"cuisine/region (Italian, Mexican, Chinese, Cajun). Generic words (food, dish) are noise.",
}

def gemma_freq():
    freq = defaultdict(Counter)
    for line in open(TR):
        r = json.loads(line)
        for a in r["attributes"]:
            e = (a.get("entity") or "").strip().lower()
            if e: freq[a["dimension"]][e] += 1
    return freq

SYS = """You normalize noisy attribute values extracted from food reviews, in ONE pass.
Given a category and its most frequent extracted values, return STRICT JSON:
{"blacklist": ["term", ...], "merges": {"canonical": ["variant", ...], ...}}
- blacklist: values that are non-discriminative noise for this category (generic praise,
  category names, first-person/cook references, fillers). These should NOT be facets.
- merges: group surface variants under one canonical form (the most natural/frequent).
  Only group genuine synonyms; do not over-merge distinct concepts.
Output JSON only, no prose."""

def call(dim, items):
    listing = ", ".join(f"{e}({c})" for e,c in items)
    user = (f"Category: {dim} -- {INTENT[dim]}\n"
            f"Most frequent extracted values (value(count)):\n{listing}\n\n"
            f"Return the one-pass blacklist and merges as JSON.")
    url = API_BASE.rstrip("/")+"/chat/completions"
    payload={"model":MODEL,"messages":[{"role":"system","content":SYS},{"role":"user","content":user}],
             "temperature":0.0,"max_tokens":1500,"reasoning_effort":"low"}
    h={"Content-Type":"application/json","Authorization":f"Bearer {API_KEY}"}
    text=None
    for attempt in range(3):
        try:
            r=requests.post(url,headers=h,json=payload,timeout=180); r.raise_for_status()
            text=(r.json()["choices"][0]["message"].get("content") or "").strip()
            if text.startswith("```"):
                text=text.strip("`")
                if text.lower().startswith("json"): text=text[4:].strip()
            return json.loads(text)
        except Exception as e:
            if attempt==2: return {"_error":str(e),"_raw":text}
            time.sleep(2**attempt)

def main():
    if not API_KEY or API_KEY=="EMPTY": sys.exit("Set NRP_API_KEY")
    freq = gemma_freq()
    out={}
    for d in DIMS:
        top = freq[d].most_common(60)
        res = call(d, top)
        bl = [x.lower() for x in res.get("blacklist",[])] if isinstance(res,dict) else []
        merges = res.get("merges",{}) if isinstance(res,dict) else {}
        # normalize merges to lowercase
        merges = {k.lower():[v.lower() for v in vs] for k,vs in merges.items()}
        out[d] = {"blacklist":bl, "merges":merges, "_error":res.get("_error") if isinstance(res,dict) else None}
        nmerge=sum(len(v) for v in merges.values())
        print(f"  {d}: blacklist={len(bl)} merges={len(merges)} canonicals ({nmerge} variants)", flush=True)
    EVAL.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False))
    print(f"Wrote {OUT}")

if __name__=="__main__":
    main()
