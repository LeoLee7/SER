"""
Mine the LLM-judge results for entities that were judged incorrect, then propose
blacklist additions per category. This realizes the 'evaluation-as-curriculum'
feedback loop: judge output drives the next iteration of the agent skill.

Rule:
  add `entity.lower()` to `dim`'s blacklist only if it appears in a
  hand-vetted seed set of well-known noise patterns identified from manual
  inspection of judge rationales. The judge-derived counts are still emitted
  to eval_data/blacklist_updates.json as evidence, but they are NOT auto-applied
  because at n=30/category many false positives arise (e.g. 'italian' was
  judged wrong twice in ingredient-modifier contexts but is a perfectly valid
  cuisine value in general).

Outputs:
  eval_data/blacklist_updates.json   - the suggestions (with rationales)
  modifies attribute_blacklist.json   - applied (a backup is written)

Idempotent: running twice with the same input file is a no-op.
"""
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = Path(__file__).resolve().parents[1]
JUDGE_FILE = PAPER / "eval_data" / "judge_results_postloop.jsonl"
BL_FILE = ROOT / "attribute_blacklist.json"
BL_FILE_SUBJDB = Path("/Users/liliu/subjective_DB/spn_datasets/food/exhibit/attribute_blacklist.json")
SUGGEST_FILE = PAPER / "eval_data" / "blacklist_updates.json"

# Seed set: terms that the manual review identified as clear noise but that
# only appear once in the small judge sample (so the >=2 rule would miss them).
# Each entry is grouped by dimension. These are well-known generic positive
# adjectives (Flavor), cook-self references (Audience), or non-meal words.
SEED_ADDS = {
    "audience_enjoyment": [
        "self", "i", "me", "we", "myself", "ourselves", "us",
    ],
    "taste_flavor": [
        "fabulous", "outstanding", "goodness", "yum", "amazing", "excellent",
        "perfect", "best", "fantastic", "awesome", "incredible", "marvelous",
        "superb", "divine", "heavenly",
    ],
    "texture_mouthfeel": [
        # mostly already covered; add a few generic positives that slipped through
        "amazing", "superbly",
    ],
    "meal_type": [
        "casual",  # not a meal-type; quality/style attribute
    ],
    "occasion_holiday": [
        # leave occasion alone; the failures are mostly proper nouns we can't
        # blanket blacklist (place names, year, etc.)
    ],
    "cuisine_type": [
        # cuisine failures are mostly modifier-vs-dish ambiguity (e.g.
        # "Italian breadcrumbs"). This is not a blacklist problem; it is a
        # prompt-level problem. We deliberately do NOT blacklist real cuisine
        # names here.
    ],
}


def derive_from_judge():
    """Entities judged wrong on >=2 distinct items."""
    counts = defaultdict(Counter)  # dim -> entity -> count_wrong
    if not JUDGE_FILE.exists():
        return counts
    with open(JUDGE_FILE) as f:
        for line in f:
            rec = json.loads(line)
            a = rec["sample"]["attribute"]
            j = rec["judgment"]
            if "error" in j:
                continue
            if not j.get("entity_correct") and not j.get("category_correct"):
                counts[a["dimension"]][a["entity"].lower()] += 1
    derived = defaultdict(list)
    for d, cnt in counts.items():
        for ent, n in cnt.items():
            if n >= 2:
                derived[d].append((ent, n))
    return derived


def main():
    with open(BL_FILE) as f:
        bl = json.load(f)

    derived = derive_from_judge()
    suggestions = {}
    applied = 0
    for d, seed_list in SEED_ADDS.items():
        before = set(x.lower() for x in bl.get(d, []))
        # Only seed adds are auto-applied. Judge-derived hits are reported
        # but require human triage (see docstring: high false-positive rate
        # at n=30/category).
        applied_now = [(t, "seed") for t in seed_list if t not in before]
        reported_only = [(ent, f"judge:{n}-wrong (NOT applied)") for (ent, n) in derived.get(d, [])
                          if ent not in [t for t, _ in applied_now] and ent not in before]
        suggestions[d] = applied_now + reported_only
        if applied_now:
            current = bl.get(d, [])
            for t, _r in applied_now:
                current.append(t)
            bl[d] = sorted(set(current))
            applied += len(applied_now)

    # backup + write both copies
    shutil.copy(BL_FILE, BL_FILE.with_suffix(".json.bak"))
    BL_FILE.write_text(json.dumps(bl, indent=2) + "\n")
    if BL_FILE_SUBJDB.exists():
        shutil.copy(BL_FILE_SUBJDB, BL_FILE_SUBJDB.with_suffix(".json.bak"))
        BL_FILE_SUBJDB.write_text(json.dumps(bl, indent=2) + "\n")

    SUGGEST_FILE.write_text(json.dumps(suggestions, indent=2) + "\n")
    print(f"Applied {applied} blacklist additions across {len([d for d,v in suggestions.items() if v])} dimensions.")
    for d, items in suggestions.items():
        if items:
            print(f"  {d}:")
            for t, src in items:
                print(f"    + {t!r:20s}  ({src})")


if __name__ == "__main__":
    main()
