"""Ground stage: keep an extracted item only if it can become a facet value.

Deterministic backstops for errors the extractor still makes after the prompt rules
(DESIGN.md, F1, F6, F7, F12). Each drop is counted by reason.

    python3 rebuild_v4/scripts/ground.py RAW.jsonl OUT.jsonl
"""
import json
import re
import sys
from collections import Counter

BLACKLIST = {d: {v.lower() for v in vs}
             for d, vs in json.load(open("/Users/liliu/SER-DB/attribute_blacklist.json")).items()}
VAGUE_AUDIENCE = {"i", "me", "myself", "we", "us", "you", "they", "them", "everyone", "everybody",
                  "all", "self", "reviewer", "people", "someone", "anyone"}
NOT_TEXTURE = {"easy", "perfectly", "nicely", "beautifully", "perfect", "good", "great", "nice", "filling"}
# Generic praise: v3 blacklist misses these. Sources: CIKM v2 judge-derived terms
# (cikm_eval/METRICS_NOTES.md, failure-cluster mining) and prompt v2 Rule 9.
GENERIC_PRAISE = {"fabulous", "outstanding", "goodness", "yum", "incredible", "marvelous", "marvellous",
                  "superb", "divine", "heavenly", "wonderful", "excellent", "best", "perfect", "perfection",
                  "just right", "very good", "so good", "really good", "tastiest", "nummy", "scrumptious",
                  "edible", "fine", "full of flavor", "flavorful", "healthy", "versatile"}
COMPARISON = re.compile(r"\b(than|like|similar to|compared)\b", re.I)


def reason(a):
    e, dim = a["entity"].strip().lower(), a["dimension"]
    if a.get("sentiment") not in ("positive", "neutral"):
        return "negative_sentiment"
    if not a.get("span"):
        return "span_not_found"
    if e in BLACKLIST.get(dim, ()):
        return "blacklist"
    if dim == "taste_flavor" and e in GENERIC_PRAISE:
        return "generic_praise"
    if dim == "audience_enjoyment" and e in VAGUE_AUDIENCE:
        return "vague_audience"
    if dim == "texture_mouthfeel" and e in NOT_TEXTURE:
        return "not_texture"
    if len(e.split()) > 3 or COMPARISON.search(e):
        return "not_a_value"
    return None


def main(src, dst):
    drops, kept = Counter(), 0
    with open(dst, "w") as f:
        for line in open(src):
            r = json.loads(line)
            keep = []
            for a in r["attributes"]:
                why = reason(a)
                if why:
                    drops[why] += 1
                else:
                    keep.append(a)
            kept += len(keep)
            f.write(json.dumps({**r, "attributes": keep}) + "\n")
    total = kept + sum(drops.values())
    print(f"kept {kept}/{total}; dropped " + ", ".join(f"{k} {v}" for k, v in drops.most_common()))


if __name__ == "__main__":
    main(*sys.argv[1:3])
