"""
Apply the v2 blacklist DIFFERENTIALLY on top of the v1 exhibit. We start from
the v1 exhibit (which was produced by the upstream create_exhibit_data.py
pipeline with min-frequency aggregation and synonym maps) and simply remove
the newly blacklisted canonical forms from each recipe's attribute lists.

This preserves all the v1 aggregation logic (which would be expensive to
re-replicate from scratch) while making the deployed exhibit reflect the v2
blacklist additions.

Inputs:
  food-exhibit-data-500recipes.json.bak.v1  (golden v1 base)
  attribute_blacklist.json                  (v2 blacklist)

Output: in-place rewrite of food-exhibit-data-500recipes.json
"""
import json
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path("/Users/liliu/SER-DB")
EXHIBIT_FILE = ROOT / "food-exhibit-data-500recipes.json"
PROCESSED_FILE = Path(
    "/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl"
)
BL_FILE = ROOT / "attribute_blacklist.json"

# Maps from internal dimension name to the per-recipe exhibit field used by the
# faceted demo (food-exhibit.css and index.html reference these field names).
DIM_TO_FIELD = {
    "taste_flavor": "taste_attributes",
    "texture_mouthfeel": "texture_attributes",
    "meal_type": "meal_type_attributes",
    "occasion_holiday": "occasion_attributes",
    "audience_enjoyment": "audience_attributes",
    "cuisine_type": "type_attributes",
}


def load_blacklist():
    with open(BL_FILE) as f:
        bl = json.load(f)
    global_bl = set(x.lower().strip() for x in bl.get("global", []))
    per_dim = {d: set(x.lower().strip() for x in bl.get(d, [])) for d in DIM_TO_FIELD}
    return per_dim, global_bl


def aggregate_per_recipe():
    """Walk the processed (post-LLM, has normalized_entity) attributes,
    apply the v2 blacklist + drop negative-sentiment, then aggregate the
    canonical entity values per recipe per dimension."""
    per_dim_bl, global_bl = load_blacklist()
    by_recipe = defaultdict(lambda: defaultdict(set))
    n_dropped_bl = n_dropped_sent = n_kept = 0
    with open(PROCESSED_FILE) as f:
        for line in f:
            r = json.loads(line)
            rid = r["recipe_id"]
            for a in r.get("attributes", []):
                d = a.get("dimension")
                if d not in DIM_TO_FIELD:
                    continue
                ent = (a.get("normalized_entity") or a.get("entity") or "").strip().lower()
                if not ent:
                    continue
                if ent in global_bl or ent in per_dim_bl.get(d, set()):
                    n_dropped_bl += 1
                    continue
                if a.get("sentiment") == "negative":
                    n_dropped_sent += 1
                    continue
                n_kept += 1
                by_recipe[rid][DIM_TO_FIELD[d]].add(ent)
    return by_recipe, dict(dropped_blacklist=n_dropped_bl, dropped_negative=n_dropped_sent, kept=n_kept)


def main():
    bak = EXHIBIT_FILE.with_suffix(".json.bak.v1")
    if not bak.exists():
        # First-run safety: snapshot current exhibit before we touch it
        shutil.copy(EXHIBIT_FILE, bak)
        print(f"Backup written: {bak}")

    # Always start from the v1 base (so reruns are idempotent)
    with open(bak) as f:
        data = json.load(f)

    per_dim_bl, global_bl = load_blacklist()
    # Combine global + per-dim into one drop set per exhibit-field name
    drop_by_field = {DIM_TO_FIELD[d]: (per_dim_bl[d] | global_bl) for d in DIM_TO_FIELD}

    n_items = len(data["items"])
    n_removed_per_field = {f: 0 for f in DIM_TO_FIELD.values()}
    for item in data["items"]:
        for field, drop in drop_by_field.items():
            before = item.get(field, []) or []
            after = sorted([v for v in before if v.lower().strip() not in drop])
            n_removed_per_field[field] += len(before) - len(after)
            item[field] = after
        all_attrs = sum((item.get(f, []) for f in DIM_TO_FIELD.values()), [])
        item["subjective_attributes"] = sorted(set(all_attrs))
        item["subjective_attribute_count"] = len(item["subjective_attributes"])

    EXHIBIT_FILE.write_text(json.dumps(data, indent=2))
    print(f"Updated {n_items} recipes.")
    print("Canonical values removed per field (v1 -> v2):")
    for f, n in n_removed_per_field.items():
        print(f"  {f}: -{n}")


if __name__ == "__main__":
    main()
