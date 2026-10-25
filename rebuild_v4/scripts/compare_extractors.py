"""Judge old (v3 demo, gemma3) vs new (v4 prompt v2, deepseek-v4-flash) extractions on the same reviews.

Old = reviews[].attributes in the v3 exhibit JSON (what the live demo shows, after
FindSpan, synonym map and blacklist). New = raw_extractions file, positive/neutral only,
span located, v3 blacklist applied (the same downstream filter old went through). Both are judged by the CIKM judge unchanged (cikm_eval/scripts/llm_judge.py:
gpt-oss, reasoning_effort low, same system prompt and dimension intents).

    python3 rebuild_v4/scripts/compare_extractors.py NEW.jsonl OUT.json
"""
import concurrent.futures as cf
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cikm_eval" / "scripts"))
import llm_judge as J  # noqa: E402

EXHIBIT = Path("/Users/liliu/SER-DB/food-exhibit-data-500recipes.json")
BLACKLIST = {d: {v.lower() for v in vs} for d, vs in json.load(open("/Users/liliu/SER-DB/attribute_blacklist.json")).items()}


def as_list(x):
    return x if isinstance(x, list) else (eval(x) if x else [])


def main(new_path, out_path):
    new = [json.loads(l) for l in open(new_path)]
    old_by_text = {}
    for item in json.load(open(EXHIBIT))["items"]:
        for rv in as_list(item["reviews"]):
            old_by_text[rv["review_text"].strip()] = rv["attributes"]
    jobs = []
    for r in new:
        old = old_by_text.get(r["review_text"].strip())
        if old is None or r["error"]:
            continue
        for a in old:
            jobs.append(("old", r["review_text"], {**a, "entity": a.get("normalized_entity") or a["entity"]}))
        for a in r["attributes"]:
            if (a.get("sentiment") in ("positive", "neutral") and a.get("span")
                    and a["entity"].lower() not in BLACKLIST.get(a["dimension"], ())):
                jobs.append(("new", r["review_text"], a))
    print(f"{len(jobs)} tuples to judge", flush=True)

    def task(job):
        side, text, a = job
        return side, a, J._call_judge(J.JUDGE_SYSTEM, J.make_user_prompt(text, a))

    rows = []
    with cf.ThreadPoolExecutor(32) as ex:
        for side, a, j in ex.map(task, jobs):
            rows.append({"side": side, "dimension": a["dimension"], "entity": a["entity"],
                         "source_text": a.get("source_text"), "judge": j})
    json.dump(rows, open(out_path, "w"), indent=1)

    stats = defaultdict(lambda: [0, 0])
    for r in rows:
        j = r["judge"]
        if "error" in j:
            continue
        ok = bool(j.get("entity_correct")) and bool(j.get("category_correct"))
        for key in ((r["side"], r["dimension"]), (r["side"], "ALL")):
            stats[key][0] += ok
            stats[key][1] += 1
    reviews = len({r["review_text"] for r in new})
    print(f"\n{'dimension':20} {'old n':>6} {'old prec':>9} {'old ok':>7} | {'new n':>6} {'new prec':>9} {'new ok':>7}   ({reviews} reviews)")
    for d in J.DIMS + ["ALL"]:
        o, n = stats[("old", d)], stats[("new", d)]
        fmt = lambda s: f"{s[1]:6} {100 * s[0] / max(s[1], 1):8.0f}% {s[0]:7}"
        print(f"{d:20} {fmt(o)} | {fmt(n)}")
    print(f"judge errors: {sum('error' in r['judge'] for r in rows)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
