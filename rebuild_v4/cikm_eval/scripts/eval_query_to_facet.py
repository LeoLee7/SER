"""
Evaluate the natural-language to facet parser against the author-curated gold set.

Metrics follow Snips/ATIS slot-filling conventions (Coucke et al. 2018):
  - per-category Slot-F1 (set-valued: micro over (category, value) pairs)
  - exact match rate (entire facet dict matches gold)
  - category activation accuracy (which categories the parser fires, binary per dim)

The parser itself runs via gpt-oss on Nautilus, but instructed to map only to the
six canonical category names. The vocabulary of canonical values per category is
auto-loaded from food-exhibit-data-500recipes.json (the post-normalization set).
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
PAPER = Path(__file__).resolve().parents[1]
GOLD_FILE = PAPER / "eval_data" / "query_to_facet_gold.json"
EXHIBIT_FILE = ROOT / "food-exhibit-data-500recipes.json"
PRED_FILE = PAPER / "eval_data" / "query_to_facet_predictions.jsonl"
OUT_TEX = PAPER / "tables" / "query_to_facet.tex"

API_BASE = os.environ.get("NRP_API_BASE", "https://ellm.nrp-nautilus.io/v1")
API_KEY = os.environ.get("NRP_API_KEY") or "EMPTY"
PARSER_MODEL = os.environ.get("PARSER_MODEL", "gpt-oss")

DIMS = ["taste_flavor", "texture_mouthfeel", "meal_type", "occasion_holiday", "audience_enjoyment", "cuisine_type"]
EXHIBIT_FIELD = {
    "taste_flavor": "taste_attributes",
    "texture_mouthfeel": "texture_attributes",
    "meal_type": "meal_type_attributes",
    "occasion_holiday": "occasion_attributes",
    "audience_enjoyment": "audience_attributes",
    "cuisine_type": "type_attributes",
}
DIM_DISPLAY = {
    "taste_flavor": "Flavor", "texture_mouthfeel": "Texture", "meal_type": "Meal Type",
    "occasion_holiday": "Occasion", "audience_enjoyment": "Audience", "cuisine_type": "Cuisine",
}


def load_vocab():
    """Per-category canonical vocabulary from the deployed EXP-DB."""
    with open(EXHIBIT_FILE) as f:
        data = json.load(f)
    vocab = {d: Counter() for d in DIMS}
    for item in data["items"]:
        for d in DIMS:
            for v in item.get(EXHIBIT_FIELD[d], []) or []:
                vocab[d][v.lower()] += 1
    return {d: sorted(vocab[d].keys()) for d in DIMS}


def build_parser_prompt(vocab):
    lines = ["You are a faceted-search query parser. Map the user's query to ONLY the six categories below, using ONLY values from the per-category vocabulary listed."]
    for d in DIMS:
        lines.append(f"\nCategory `{d}` (canonical values, lowercase): {', '.join(vocab[d][:60])}{' ...' if len(vocab[d])>60 else ''}")
    lines.append(
        "\nRules:\n"
        "- Use only the canonical values shown above; do not invent new values.\n"
        "- Omit categories that the query does not mention.\n"
        "- Use plural→singular and morphological variants if they match a canonical (e.g., 'kids' is canonical here).\n"
        "- Return STRICT JSON with category keys and a list of string values, e.g., {\"meal_type\": [\"dinner\"], \"audience_enjoyment\": [\"kids\"]}.\n"
        "- Do not include any prose outside the JSON.\n"
    )
    return "\n".join(lines)


def call_parser(system_prompt: str, query: str, retries=3) -> dict:
    url = API_BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": PARSER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query!r}\nOutput JSON only."},
        ],
        "temperature": 0.0,
        "max_tokens": 600,
        "reasoning_effort": "low",
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    text = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            text = (resp.json()["choices"][0]["message"].get("content") or "").strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            return json.loads(text)
        except Exception as e:
            if attempt == retries - 1:
                return {"_error": str(e), "_raw": text}
            time.sleep(2 ** attempt)


def cmd_run():
    if not API_KEY or API_KEY == "EMPTY":
        sys.exit("Set NRP_API_KEY env var before running.")
    with open(GOLD_FILE) as f:
        gold_data = json.load(f)
    vocab = load_vocab()
    system_prompt = build_parser_prompt(vocab)

    PRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PRED_FILE, "w") as out:
        for q in gold_data["queries"]:
            pred = call_parser(system_prompt, q["text"])
            out.write(json.dumps({"id": q["id"], "text": q["text"], "gold": q["gold"], "pred": pred}) + "\n")
            out.flush()
            print(f"  {q['id']:5s} {q['text']!r}\n         gold={q['gold']}\n         pred={pred}")


def cmd_aggregate():
    """Compute slot-F1 micro-averaged across (category, value) pairs + exact-match."""
    with open(PRED_FILE) as f:
        rows = [json.loads(l) for l in f]

    # Micro Slot-F1: union of (category, value) pairs
    per_cat_tp = Counter(); per_cat_fp = Counter(); per_cat_fn = Counter()
    exact_match = 0
    for r in rows:
        gold = r["gold"]; pred = r["pred"] if isinstance(r["pred"], dict) else {}
        # exact match: per-cat sorted lists equal
        norm_gold = {k: sorted(v) for k, v in gold.items() if v}
        norm_pred = {k: sorted([x.lower() for x in (pred.get(k) or [])]) for k in DIMS if pred.get(k)}
        if norm_gold == norm_pred:
            exact_match += 1
        for d in DIMS:
            g = set(gold.get(d, []) or [])
            p = set([x.lower() for x in (pred.get(d, []) or [])])
            per_cat_tp[d] += len(g & p)
            per_cat_fp[d] += len(p - g)
            per_cat_fn[d] += len(g - p)

    def prf(tp, fp, fn):
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        f1 = 0 if p + r == 0 else 2 * p * r / (p + r)
        return p, r, f1

    lines = []
    a = lines.append
    a("% Auto-generated by scripts/eval_query_to_facet.py")
    a("\\begin{table}[t]")
    a("\\centering")
    a("\\small")
    a("\\begin{tabular}{@{}lrrr@{}}")
    a("\\toprule")
    a("\\textbf{Category} & \\textbf{P} & \\textbf{R} & \\textbf{F1} \\\\")
    a("\\midrule")
    total_tp = total_fp = total_fn = 0
    for d in DIMS:
        tp, fp, fn = per_cat_tp[d], per_cat_fp[d], per_cat_fn[d]
        total_tp += tp; total_fp += fp; total_fn += fn
        p, r, f1 = prf(tp, fp, fn)
        a(f"{DIM_DISPLAY[d]} & {100*p:.1f} & {100*r:.1f} & {100*f1:.1f} \\\\")
    a("\\midrule")
    p, r, f1 = prf(total_tp, total_fp, total_fn)
    a(f"\\textbf{{Micro}} & \\textbf{{{100*p:.1f}}} & \\textbf{{{100*r:.1f}}} & \\textbf{{{100*f1:.1f}}} \\\\")
    a("\\midrule")
    em_pct = 100 * exact_match / max(len(rows), 1)
    a(f"\\multicolumn{{4}}{{l}}{{Exact-match rate (all categories simultaneously correct): \\textbf{{{em_pct:.1f}\\%}} ({exact_match}/{len(rows)})}} \\\\")
    a("\\bottomrule")
    a("\\end{tabular}")
    a("\\caption{Query-to-facet parser accuracy on $n=" + str(len(rows)) + "$ author-curated subjective queries. "
      "Metrics follow slot-filling conventions in Snips/ATIS~\\cite{coucke2018snips}: per-category precision and recall over the set of canonical facet values, "
      "with micro-average across categories and an exact-match rate that requires the parser to produce the complete gold facet dictionary.}")
    a("\\label{tab:q2f}")
    a("\\end{table}")
    OUT_TEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_TEX.write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_TEX}")
    print(f"\nExact-match: {exact_match}/{len(rows)} = {em_pct:.1f}%")
    print(f"Micro P/R/F1: {100*p:.1f}/{100*r:.1f}/{100*f1:.1f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": cmd_run, "aggregate": cmd_aggregate}[cmd]()
