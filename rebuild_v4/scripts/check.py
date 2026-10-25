"""Flag rule violations in an extraction file. Usage: python3 check.py FILE [FILE ...]"""
import json, re, sys
PRON = {"i", "me", "myself", "we", "us", "you", "they", "them", "everyone", "self", "reviewer"}
NOT_TEXTURE = {"easy", "perfectly", "nicely", "beautifully", "perfect", "good", "great", "nice", "warm", "filling"}
BRANDS = re.compile(r"panera|pizza hut|olive garden|kfc|mcdonald|starbucks|applebee|restaurant|takeout|copycat", re.I)
VERBISH = re.compile(r"\b(love|loved|like|liked|taste better|tastes like|needed|will|would|next time|added|used)\b", re.I)
for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path)]
    flags, n = {}, 0
    for r in rows:
        for a in r["attributes"]:
            n += 1
            e, dim = a["entity"].strip(), a["dimension"]
            def f(k): flags.setdefault(k, []).append(f"{dim[:5]}:{e}")
            if len(e.split()) > 3: f("long>3w")
            if VERBISH.search(e): f("verb/phrase")
            if dim == "audience_enjoyment" and e.lower() in PRON: f("pronoun-audience")
            if dim == "texture_mouthfeel" and e.lower() in NOT_TEXTURE: f("non-texture")
            if dim == "cuisine_type" and BRANDS.search(e): f("brand-cuisine")
            if dim in ("occasion_holiday", "meal_type", "audience_enjoyment") and a.get("sentiment") == "negative": f("neg-context")
            if a.get("span") is None: f("no-span")
    print(f"{path.split('/')[-1]}: {len(rows)} reviews, {n} items, errors={sum(1 for r in rows if r['error'])}")
    for k, v in sorted(flags.items()): print(f"   {k:16} {len(v):3}  {v[:8]}")
