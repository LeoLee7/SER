"""Verify stage: second pass, the extractor model checks each grounded candidate against the rubric.

    python3 rebuild_v4/scripts/verify.py GROUNDED.jsonl OUT.jsonl [--prompt verify_prompt_v1]
"""
import argparse, concurrent.futures as cf, json, os, time, urllib.request
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BASE, KEY, MODEL = os.environ["NRP_API_BASE"], os.environ["NRP_API_KEY"], "deepseek-v4-flash"

def call(prompt, user, retries=4):
    body = {"model": MODEL, "temperature": 0.0, "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": False, "thinking": False},
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user}]}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE + "/chat/completions", json.dumps(body).encode(),
                                         {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
            c = json.load(urllib.request.urlopen(req, timeout=180))["choices"][0]["message"]["content"] or ""
            return json.JSONDecoder().raw_decode(c[c.find("["):])[0], None
        except Exception as e:
            err = str(e)[:200]; time.sleep(2 ** attempt * 3)
    return None, err

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--prompt", default="verify_prompt_v1"); args = ap.parse_args()
    prompt = (ROOT / "prompts" / f"{args.prompt}.md").read_text()
    rows = [json.loads(l) for l in open(args.src)]
    def work(r):
        if not r["attributes"]:
            return {**r, "verify_error": None}
        cands = [{"id": i, "category": a["dimension"], "value": a["entity"], "evidence": a["source_text"]}
                 for i, a in enumerate(r["attributes"])]
        out, err = call(prompt, f"Review:\n{r['review_text']}\n\nCandidates:\n{json.dumps(cands)}")
        if out is None:  # fail open: keep everything, record the error
            return {**r, "verify_error": err}
        verdict = {o.get("id"): o for o in out if isinstance(o, dict)}
        keep = []
        for i, a in enumerate(r["attributes"]):
            v = verdict.get(i, {"keep": True})
            if v.get("keep", True): keep.append(a)
            else: drops[v.get("code")] += 1
        return {**r, "attributes": keep, "verify_error": None}
    drops = Counter()
    with cf.ThreadPoolExecutor(24) as ex, open(args.dst, "w") as f:
        for res in ex.map(work, rows): f.write(json.dumps(res) + "\n")
    print("verify drops:", drops.most_common())

if __name__ == "__main__":
    main()
