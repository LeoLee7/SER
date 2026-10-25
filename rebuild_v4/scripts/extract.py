"""v4 extraction: prompt v2 on the NRP Nautilus endpoint, thinking off.

Resumable: rows already in the output file (keyed by recipe_id, review_idx) are skipped.

    python3 rebuild_v4/scripts/extract.py --limit 10 --out rebuild_v4/data/sample10.jsonl
    python3 rebuild_v4/scripts/extract.py            # full 10,000 reviews
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT = Path("/Users/liliu/subjective_DB/spn_datasets/food/data/subset_500recipes_20reviews.json")
PROMPT_NAME = "extraction_prompt_v2"
PROMPT = ""
MODEL = "deepseek-v4-flash"
BASE = os.environ["NRP_API_BASE"]
KEY = os.environ["NRP_API_KEY"]
DIMENSIONS = {"taste_flavor", "texture_mouthfeel", "meal_type", "occasion_holiday",
              "audience_enjoyment", "cuisine_type"}


def load_reviews():
    rows = []
    for recipe in json.load(open(INPUT)):
        for idx, rev in enumerate(recipe["reviews"]):
            rows.append({"recipe_id": recipe["recipe_id"], "recipe_name": recipe["name"],
                         "recipe_category": recipe["category"], "review_idx": idx,
                         "review_id": rev["review_id"], "rating": rev["rating"],
                         "review_text": rev["review"]})
    return rows


def span(source, text):
    start = text.lower().find((source or "").lower())
    return None if not source or start < 0 else {"start": start, "end": start + len(source)}


def call(text, retries=4):
    body = {"model": MODEL, "temperature": 0.2, "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": False, "thinking": False},
            "messages": [{"role": "user", "content": PROMPT + "\n\n" + text}]}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", json.dumps(body).encode(),
                                         {"Authorization": "Bearer " + KEY,
                                          "Content-Type": "application/json"})
            content = json.load(urllib.request.urlopen(req, timeout=90))["choices"][0]["message"]["content"] or ""
            start = content.find("[")
            if start < 0:
                return [], None
            return json.JSONDecoder().raw_decode(content[start:])[0], None
        except Exception as e:  # network, 429, or unparseable JSON
            err = str(e)[:200]
            time.sleep(2 ** attempt * 3)
    return [], err


def process(row):
    attrs, err = call(row["review_text"])
    kept = []
    for a in attrs if isinstance(attrs, list) else []:
        if not isinstance(a, dict) or a.get("dimension") not in DIMENSIONS or not a.get("entity"):
            continue
        a["span"] = span(a.get("source_text"), row["review_text"])
        kept.append(a)
    return {**row, "model": MODEL, "prompt": PROMPT_NAME, "error": err, "attributes": kept}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "raw_extractions_v4.jsonl"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--prompt", default="extraction_prompt_v2")
    ap.add_argument("--ids", help="JSON list of {recipe_id, review_idx} to run instead of all reviews")
    args = ap.parse_args()
    global PROMPT, PROMPT_NAME
    PROMPT_NAME = args.prompt
    PROMPT = (ROOT / "prompts" / f"{args.prompt}.md").read_text()

    rows = load_reviews()
    if args.ids:
        want = {(x["recipe_id"], x["review_idx"]) for x in json.load(open(args.ids))}
        rows = [r for r in rows if (r["recipe_id"], r["review_idx"]) in want]
    if args.limit:
        rows = rows[::len(rows) // args.limit][:args.limit]
    out = Path(args.out)
    done = set()
    if out.exists():
        for line in open(out):
            r = json.loads(line)
            if not r["error"]:
                done.add((r["recipe_id"], r["review_idx"]))
    todo = [r for r in rows if (r["recipe_id"], r["review_idx"]) not in done]
    print(f"{len(rows)} reviews, {len(done)} done, {len(todo)} to run", flush=True)

    lock, t0, n = threading.Lock(), time.time(), 0
    with open(out, "a") as f, cf.ThreadPoolExecutor(args.workers) as ex:
        for fut in cf.as_completed([ex.submit(process, r) for r in todo]):
            result = fut.result()
            with lock:
                f.write(json.dumps(result) + "\n")
                f.flush()
                n += 1
                if n % 200 == 0:
                    print(f"{n}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    print(f"finished {n} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
