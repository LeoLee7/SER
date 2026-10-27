"""
LLM-as-a-Judge evaluation of Gemma-3 attribute extraction.

Protocol follows Zheng et al. NeurIPS 2024 (cross-family judge) and tuple-level
evaluation conventions from ABSA-Quad (Cai et al. ACL 2021): for each extracted
(category, entity, sentiment, source_text) tuple we score four binary fields.

Judge: gpt-oss on the NRP-Nautilus endpoint (different model family from the
Gemma-3 extractor, hosted on the same infrastructure for reproducibility).

Usage:
  # 1. Build a stratified sample (no API calls):
  python3 scripts/llm_judge.py sample --per-category 30 --seed 42

  # 2. Dry-run: render prompts to eval_data/judge_prompts.jsonl for inspection.
  python3 scripts/llm_judge.py dryrun

  # 3. Actually call gpt-oss and write per-item judgments:
  python3 scripts/llm_judge.py run

  # 4. Aggregate into tables/llm_judge.tex
  python3 scripts/llm_judge.py aggregate
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests  # gpt-oss endpoint is OpenAI-compatible REST

ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = PAPER_DIR / "eval_data"
TABLES_DIR = PAPER_DIR / "tables"

# Extraction stages (data lineage):
#   trulyraw = direct Gemma-3 output, BEFORE FindSpan grounding (includes
#              hallucinated spans) and BEFORE any normalization. No span field.
#   raw      = after FindSpan grounding, entity field judged (pre-normalization
#              entity text); this is what we previously labelled "Raw".
#   postloop = after blacklist filtering + canonical synonym mapping.
SUBJDB_DATA = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data")
TRULYRAW_FILE = SUBJDB_DATA / "extracted_attributes_500recipes.jsonl"
RAW_FILE = ROOT / "processed_attributes_500recipes.jsonl"
POSTLOOP_FILE = SUBJDB_DATA / "processed_attributes_500recipes.jsonl"
BLACKLIST_FILE = ROOT / "attribute_blacklist.json"

# Per-mode file paths (with optional tag, e.g. 'v1', 'v2').
def mode_paths(mode: str, tag: str = ""):
    parts = []
    if mode != "raw": parts.append(mode)
    if tag: parts.append(tag)
    suffix = "_" + "_".join(parts) if parts else ""
    return {
        "sample": EVAL_DIR / f"judge_sample{suffix}.jsonl",
        "prompts": EVAL_DIR / f"judge_prompts{suffix}.jsonl",
        "judgments": EVAL_DIR / f"judge_results{suffix}.jsonl",
        "table": TABLES_DIR / f"llm_judge{suffix}.tex",
    }

# Default paths (raw); overridden via --mode.
SAMPLE_FILE = EVAL_DIR / "judge_sample.jsonl"
PROMPTS_FILE = EVAL_DIR / "judge_prompts.jsonl"
JUDGMENTS_FILE = EVAL_DIR / "judge_results.jsonl"

# Nautilus endpoint - same infra as the Gemma-3 extractor, different model family.
API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or os.environ.get("nrp_llm_key") or "EMPTY"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-oss")
REASONING_EFFORT = os.environ.get("JUDGE_REASONING_EFFORT", "low")

DIMS = [
    "taste_flavor",
    "texture_mouthfeel",
    "meal_type",
    "occasion_holiday",
    "audience_enjoyment",
    "cuisine_type",
]

DIM_INTENT = {
    "taste_flavor": "the taste or flavor profile of the food (e.g., sweet, tangy, savory). NOT general quality words like 'good', 'delicious', 'great'.",
    "texture_mouthfeel": "the physical mouthfeel or consistency (e.g., tender, crispy, moist, creamy).",
    "meal_type": "the meal or dish role (e.g., breakfast, dinner, dessert, side-dish, appetizer).",
    "occasion_holiday": "a specific occasion, event, or holiday for serving (e.g., Christmas, birthday, potluck, weeknight). NOT a general meal time.",
    "audience_enjoyment": "WHO ENJOYED EATING the dish, not who cooked it. So 'I' or 'me' or 'we' referring to the reviewer themselves is INCORRECT; 'husband', 'kids', 'guests', 'family' are CORRECT.",
    "cuisine_type": "the cuisine style or cultural/regional origin (e.g., Italian, Mexican, Chinese, Cajun).",
}


JUDGE_SYSTEM = """You are an expert annotator evaluating attribute extractions from food recipe reviews.
You are NOT generating new annotations; you are JUDGING existing ones.
For each (category, entity, sentiment, source_text) tuple, decide if each field is correct given the review.

Definitions:
- entity_correct = true iff the extracted entity word/phrase is a sensible, in-context attribute of the named category, derived from the source_text. It should NOT be a generic noise word, NOT a meta-comment, and NOT mis-categorized.
- category_correct = true iff the entity actually belongs to the named category given the source_text.
- sentiment_correct = true iff the sentiment label matches the source_text sentiment toward the entity.
- span_faithful = true iff source_text is verbatim taken from the review (substring match, ignoring HTML escapes).

For audience_enjoyment specifically: 'I', 'me', 'we', 'my' referring to the reviewer COOKING the dish should be marked entity_correct=false (cook-vs-audience confusion).

Return STRICT JSON of the form:
{"entity_correct": <bool>, "category_correct": <bool>, "sentiment_correct": <bool>, "span_faithful": <bool>, "rationale": "<one short sentence>"}
No prose outside the JSON.
"""


def make_user_prompt(review_text: str, attr: dict) -> str:
    return (
        f"Review:\n{review_text}\n\n"
        f"Extraction to judge:\n"
        f"  category = {attr['dimension']}  ({DIM_INTENT.get(attr['dimension'], '')})\n"
        f"  entity = {attr['entity']!r}\n"
        f"  sentiment = {attr.get('sentiment','?')}\n"
        f"  source_text = {attr.get('source_text','?')!r}\n\n"
        f"Output JSON only."
    )


def _load_blacklist():
    with open(BLACKLIST_FILE) as f:
        bl = json.load(f)
    global_bl = set(x.lower() for x in bl.get("global", []))
    per_dim = {d: set(x.lower() for x in bl.get(d, [])) for d in DIMS}
    return per_dim, global_bl


def load_source(mode: str):
    """Load attribute tuples. For 'raw' use the pre-loop file. For 'postloop'
    use the file with normalized_entity and additionally filter by blacklist
    + drop negative sentiment, mirroring the deployed exhibit construction."""
    src_file = {"postloop": POSTLOOP_FILE, "trulyraw": TRULYRAW_FILE}.get(mode, RAW_FILE)
    if not src_file.exists():
        sys.exit(f"Source file not found: {src_file}")
    rows = []
    with open(src_file) as f:
        for line in f:
            rows.append(json.loads(line))
    if mode != "postloop":
        # trulyraw and raw both judge the original entity text as-is.
        return rows, mode
    # Apply the same blacklist + sentiment rules used by create_exhibit_data.py.
    per_dim_bl, global_bl = _load_blacklist()
    filtered_rows = []
    n_dropped_bl = n_dropped_sent = 0
    for r in rows:
        kept = []
        for a in r.get("attributes", []):
            d = a.get("dimension")
            ent = (a.get("normalized_entity") or a.get("entity") or "").strip().lower()
            if ent in global_bl or ent in per_dim_bl.get(d, set()):
                n_dropped_bl += 1; continue
            if a.get("sentiment") == "negative":
                n_dropped_sent += 1; continue
            # rewrite display entity to its normalized form for downstream judging
            a = dict(a); a["entity"] = a.get("normalized_entity") or a["entity"]
            kept.append(a)
        if kept:
            nr = dict(r); nr["attributes"] = kept
            filtered_rows.append(nr)
    print(f"  postloop filter: dropped {n_dropped_bl} blacklisted, {n_dropped_sent} negative-sentiment", flush=True)
    return filtered_rows, "postloop"


def cmd_sample(args):
    """Stratified sample: N per dimension."""
    rng = random.Random(args.seed)
    rows, mode = load_source(args.mode)
    by_dim = defaultdict(list)
    for r in rows:
        for a in r.get("attributes", []):
            by_dim[a["dimension"]].append((r, a))

    paths = mode_paths(args.mode, getattr(args, "tag", ""))
    sample_file = paths["sample"]
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(sample_file, "w") as out:
        for d in DIMS:
            pool = by_dim.get(d, [])
            picked = rng.sample(pool, min(args.per_category, len(pool)))
            for r, a in picked:
                item = {
                    "recipe_id": r["recipe_id"],
                    "recipe_name": r["recipe_name"],
                    "review_idx": r["review_idx"],
                    "review_text": r["review_text"],
                    "attribute": a,
                    "mode": args.mode,
                }
                out.write(json.dumps(item) + "\n")
            print(f"  {d}: sampled {len(picked)}/{len(pool)}")
    print(f"Wrote {sample_file}")


def cmd_dryrun(args):
    """Render judge prompts without calling the API."""
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_FILE) as fin, open(PROMPTS_FILE, "w") as fout:
        for line in fin:
            item = json.loads(line)
            prompt = make_user_prompt(item["review_text"], item["attribute"])
            fout.write(json.dumps({"sample": item, "system": JUDGE_SYSTEM, "user": prompt}) + "\n")
    print(f"Wrote {PROMPTS_FILE}")
    print("Inspect a few entries before running 'python3 scripts/llm_judge.py run'.")


def _call_judge(system: str, user: str, model: str = JUDGE_MODEL, max_retries: int = 3) -> dict:
    """Call gpt-oss on Nautilus (OpenAI-compatible REST). Returns parsed JSON or {'error': ...}."""
    url = API_BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": 800,
        "reasoning_effort": REASONING_EFFORT,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    text = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            body = resp.json()
            text = (body.get("choices", [{}])[0].get("message", {}) or {}).get("content") or ""
            text = text.strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            return json.loads(text)
        except Exception as e:
            if attempt == max_retries - 1:
                return {"error": str(e), "raw": text}
            time.sleep(2 ** attempt)


def cmd_run(args):
    """Call gpt-oss concurrently for each sampled item; write judgments. Resumable."""
    if not API_KEY or API_KEY == "EMPTY":
        sys.exit("Set NRP_API_KEY env var before running.")

    paths = mode_paths(args.mode, getattr(args, "tag", ""))
    sample_file = paths["sample"]
    judgments_file = paths["judgments"]

    done_keys = set()
    if judgments_file.exists() and not args.overwrite:
        with open(judgments_file) as f:
            for line in f:
                rec = json.loads(line)
                s = rec["sample"]; a = s["attribute"]
                done_keys.add((s["recipe_id"], s["review_idx"], a["entity"], a["dimension"]))
        mode = "a"
    else:
        mode = "w"

    # collect pending items
    pending = []
    with open(sample_file) as fin:
        for line in fin:
            item = json.loads(line)
            a = item["attribute"]
            key = (item["recipe_id"], item["review_idx"], a["entity"], a["dimension"])
            if key in done_keys:
                continue
            pending.append(item)

    n_total = len(pending) + len(done_keys)
    n_pending = len(pending)
    print(f"Resuming: {len(done_keys)} done, {n_pending} pending, workers={args.workers}", flush=True)

    write_lock = threading.Lock()
    counter = {"done": len(done_keys)}

    def task(item):
        a = item["attribute"]
        user = make_user_prompt(item["review_text"], a)
        j = _call_judge(JUDGE_SYSTEM, user)
        return item, j

    with open(judgments_file, mode) as fout, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(task, it) for it in pending]
        for fut in as_completed(futures):
            item, judgment = fut.result()
            a = item["attribute"]
            with write_lock:
                fout.write(json.dumps({"sample": item, "judgment": judgment}) + "\n")
                fout.flush()
                counter["done"] += 1
                err = "ERR" if "error" in judgment else "ok "
                print(f"  [{counter['done']}/{n_total}] {err} {a['dimension']:20s} entity={a['entity']!r:25s}", flush=True)


def cmd_aggregate(args):
    """Aggregate judge_results into per-category precision and tuple precision."""
    paths = mode_paths(args.mode, getattr(args, "tag", ""))
    judgments_file = paths["judgments"]
    table_path = paths["table"]
    by_dim = defaultdict(lambda: {"n":0, "entity":0, "category":0, "sentiment":0, "span":0, "tuple":0, "errors":0})
    with open(judgments_file) as f:
        for line in f:
            rec = json.loads(line)
            d = rec["sample"]["attribute"]["dimension"]
            j = rec["judgment"]
            if "error" in j:
                by_dim[d]["errors"] += 1
                continue
            ec = bool(j.get("entity_correct"))
            cc = bool(j.get("category_correct"))
            sc = bool(j.get("sentiment_correct"))
            spf = bool(j.get("span_faithful"))
            by_dim[d]["n"] += 1
            by_dim[d]["entity"] += int(ec)
            by_dim[d]["category"] += int(cc)
            by_dim[d]["sentiment"] += int(sc)
            by_dim[d]["span"] += int(spf)
            by_dim[d]["tuple"] += int(ec and cc and sc and spf)

    # render LaTeX table
    DIM_DISPLAY = {
        "taste_flavor": "Flavor",
        "texture_mouthfeel": "Texture",
        "meal_type": "Meal Type",
        "occasion_holiday": "Occasion",
        "audience_enjoyment": "Audience",
        "cuisine_type": "Cuisine Type",
    }

    lines = []
    a = lines.append
    a("% Auto-generated by scripts/llm_judge.py aggregate.")
    a("\\begin{table}[t]")
    a("\\centering")
    a("\\small")
    a("\\begin{tabular}{@{}lrrrrr@{}}")
    a("\\toprule")
    a("\\textbf{Dimension} & $n$ & \\textbf{P(ent)} & \\textbf{P(cat)} & \\textbf{P(sent)} & \\textbf{P(tuple)} \\\\")
    a("\\midrule")
    totals = Counter()
    for d in DIMS:
        s = by_dim[d]
        if s["n"] == 0:
            a(f"{DIM_DISPLAY[d]} & 0 & -- & -- & -- & -- \\\\")
            continue
        n = s["n"]
        p_e = 100*s["entity"]/n
        p_c = 100*s["category"]/n
        p_s = 100*s["sentiment"]/n
        p_t = 100*s["tuple"]/n
        a(f"{DIM_DISPLAY[d]} & {n} & {p_e:.1f} & {p_c:.1f} & {p_s:.1f} & {p_t:.1f} \\\\")
        for k in ("n","entity","category","sentiment","span","tuple"):
            totals[k] += s[k]
    a("\\midrule")
    if totals["n"]:
        n = totals["n"]
        a(f"\\textbf{{Macro}} & {n} & {100*totals['entity']/n:.1f} & {100*totals['category']/n:.1f} & {100*totals['sentiment']/n:.1f} & {100*totals['tuple']/n:.1f} \\\\")
    a("\\bottomrule")
    a("\\end{tabular}")
    a("\\caption{LLM-as-a-Judge evaluation of Gemma-3 extractions on a stratified sample. "
      "Judge: gpt-oss~\\cite{openai2025gptoss} on the NRP-Nautilus endpoint (different model family from the extractor), "
      "following the cross-family protocol of Zheng et al.~\\cite{zheng2024judging}. "
      "Tuple-level scoring follows ABSA-Quad conventions~\\cite{cai2021aspect}: \\emph{P(tuple)} requires all four fields "
      "(entity, category, sentiment, span) to be judged correct simultaneously.}")
    a("\\label{tab:llm-judge}")
    a("\\end{table}")
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    table_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {table_path}")
    print(json.dumps({k: dict(v) for k, v in by_dim.items()}, indent=2))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("--per-category", type=int, default=30); s.add_argument("--seed", type=int, default=42); s.add_argument("--mode", choices=["raw","postloop","trulyraw"], default="raw"); s.add_argument("--tag", default="")
    d = sub.add_parser("dryrun"); d.add_argument("--mode", choices=["raw","postloop","trulyraw"], default="raw"); d.add_argument("--tag", default="")
    r = sub.add_parser("run"); r.add_argument("--overwrite", action="store_true"); r.add_argument("--workers", type=int, default=8); r.add_argument("--mode", choices=["raw","postloop","trulyraw"], default="raw"); r.add_argument("--tag", default="")
    ag = sub.add_parser("aggregate"); ag.add_argument("--mode", choices=["raw","postloop","trulyraw"], default="raw"); ag.add_argument("--tag", default="")
    args = p.parse_args()
    {"sample": cmd_sample, "dryrun": cmd_dryrun, "run": cmd_run, "aggregate": cmd_aggregate}[args.cmd](args)


if __name__ == "__main__":
    main()
