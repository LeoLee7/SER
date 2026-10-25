"""
Global concept-coverage analysis across all six categories.

We validated on three judged concepts (scripts/eval_pr_concept.py) that the
coverage expansion from keyword -> extraction -> normalization is genuine recall
gain at roughly constant precision. This script measures that same coverage
expansion deterministically (no LLM judge) for the top-N canonical concepts in
EVERY category, so we can see the global distribution and per-category variance
rather than three anecdotes.

For each canonical concept c in a category we count the recipes its index covers
at three pipeline stages:
  kw    = recipes whose reviews contain the exact word c (whole-word)
  gemma = recipes with a raw Gemma entity == c (LLM extraction, pre-normalization)
  v1    = recipes with normalized_entity == c (after normalization)
and report, per concept, the share of the v1 (deployed) set that a literal keyword
search misses:  miss% = 1 - |kw & v1| / |v1|, decomposed into the part recovered by
extraction (gemma) vs by normalization.

Outputs:
  tables/coverage_global.tex          per-category summary (median miss%, IQR, multiplier)
  images/coverage_global.pdf          box plot of miss% distribution per category
  eval_data/coverage_global.json      per-concept raw numbers
"""
import json, re, statistics as st
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/Users/liliu/SER-DB")
PAPER = Path(__file__).resolve().parents[1]
TABLES = PAPER / "tables"; IMAGES = PAPER / "images"; EVAL = PAPER / "eval_data"
TRULYRAW = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
PROC = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl")

DIMS = ["taste_flavor","texture_mouthfeel","meal_type","occasion_holiday","audience_enjoyment","cuisine_type"]
DISP = {"taste_flavor":"Flavor","texture_mouthfeel":"Texture","meal_type":"Meal","occasion_holiday":"Occasion","audience_enjoyment":"Audience","cuisine_type":"Cuisine"}
TOPN = 20
MIN_SUPPORT = 5   # ignore ultra-rare canonicals (unstable percentages)


def load():
    recipe_text = {}                                  # rid -> concatenated lowercased reviews
    gemma = defaultdict(lambda: defaultdict(set))     # rid -> dim -> set(entity)
    v1 = defaultdict(lambda: defaultdict(set))        # rid -> dim -> set(normalized)
    v1_freq = defaultdict(lambda: defaultdict(int))   # dim -> canon -> #recipes
    seen = set()
    text_parts = defaultdict(list)
    for line in open(TRULYRAW):
        r = json.loads(line); rid = r["recipe_id"]; ridx = r["review_idx"]
        if (rid,ridx) not in seen:
            text_parts[rid].append(r["review_text"].lower()); seen.add((rid,ridx))
        for a in r["attributes"]:
            gemma[rid][a["dimension"]].add((a.get("entity") or "").strip().lower())
    for rid,parts in text_parts.items():
        recipe_text[rid] = "\n".join(parts)
    for line in open(PROC):
        r = json.loads(line); rid = r["recipe_id"]
        local = defaultdict(set)
        for a in r["attributes"]:
            d=a["dimension"]; ne=(a.get("normalized_entity") or "").strip().lower()
            if not ne: continue
            v1[rid][d].add(ne); local[d].add(ne)
        for d,s in local.items():
            for ne in s: v1_freq[d][ne]+=1
    return recipe_text, gemma, v1, v1_freq


def covers_literal(recipe_text, word):
    # Fair keyword baseline: match the canonical with hyphen OR space (so the
    # baseline is not handicapped by canonical hyphenation like "side-dish"),
    # and also the de-hyphenated single token.
    forms = {word, word.replace("-", " "), word.replace("-", ""), word.replace(" ", "-")}
    pats = [re.compile(r"\b"+re.escape(f)+r"\b") for f in forms if f]
    return {rid for rid,txt in recipe_text.items() if any(p.search(txt) for p in pats)}


def main():
    recipe_text, gemma, v1, v1_freq = load()
    per_concept = []   # (dim, concept, kw, gemma, v1, miss_pct, ext_pct, norm_pct)
    for d in DIMS:
        concepts = [c for c,n in sorted(v1_freq[d].items(), key=lambda x:-x[1]) if n>=MIN_SUPPORT][:TOPN]
        for c in concepts:
            v1set = {rid for rid,dd in v1.items() if c in dd.get(d,set())}
            if not v1set: continue
            gset = {rid for rid,dd in gemma.items() if c in dd.get(d,set())} & v1set
            kwset = covers_literal(recipe_text, c) & v1set
            v1n=len(v1set)
            miss = 100*(v1n - len(kwset))/v1n
            # decomposition of the v1 set coverage:
            #   covered by keyword            = |kw & v1|
            #   added by extraction beyond kw = |gemma & v1| - |kw & v1|   (clip >=0)
            #   added by normalization        = |v1| - |gemma & v1|
            ext_added = max(len(gset)-len(kwset),0)
            norm_added = v1n - len(gset)
            per_concept.append({
                "dim":d,"concept":c,"kw":len(kwset),"gemma":len(gset),"v1":v1n,
                "miss_pct":miss,
                "ext_added_pct":100*ext_added/v1n,
                "norm_added_pct":100*norm_added/v1n,
            })
    EVAL.mkdir(parents=True,exist_ok=True)
    (EVAL/"coverage_global.json").write_text(json.dumps(per_concept,indent=2))

    # per-category aggregate
    bycat = defaultdict(list)
    for r in per_concept: bycat[r["dim"]].append(r)

    # ---- table ----
    L=[]; a=L.append
    a("% Auto-generated by scripts/eval_coverage_global.py")
    a("\\begin{table}[t]"); a("\\centering"); a("\\small"); a("\\setlength{\\tabcolsep}{4pt}")
    a("\\begin{tabular}{@{}lrrrr@{}}")
    a("\\toprule")
    a("\\textbf{Category} & \\textbf{\\#concepts} & \\textbf{median} & \\textbf{IQR} & \\textbf{median} \\\\")
    a(" & \\textbf{(top-N)} & \\textbf{miss\\%} & \\textbf{miss\\%} & \\textbf{SER/kw $\\times$} \\\\")
    a("\\midrule")
    allmiss=[]
    for d in DIMS:
        rs=bycat[d]
        if not rs: a(f"{DISP[d]} & 0 & -- & -- & -- \\\\"); continue
        miss=[r["miss_pct"] for r in rs]; allmiss+=miss
        mult=[(r["v1"]/r["kw"]) for r in rs if r["kw"]>0]
        q1=st.quantiles(miss,n=4)[0] if len(miss)>1 else miss[0]
        q3=st.quantiles(miss,n=4)[2] if len(miss)>1 else miss[0]
        a(f"{DISP[d]} & {len(rs)} & {st.median(miss):.0f} & {q1:.0f}--{q3:.0f} & {st.median(mult):.2f} \\\\")
    a("\\midrule")
    a(f"\\textbf{{All}} & {len(per_concept)} & \\textbf{{{st.median(allmiss):.0f}}} & -- & -- \\\\")
    a("\\bottomrule"); a("\\end{tabular}")
    a("\\caption{Global concept-coverage gain across all six categories "
      f"(top-{TOPN} canonical concepts per category, support $\\geq{MIN_SUPPORT}$ recipes). "
      "\\emph{miss\\%} is the share of recipes the deployed facet surfaces that a literal "
      "exact-word search misses, because reviewers use synonymous surface forms. "
      "We validated on three judged concepts that this coverage expansion is genuine "
      "recall gain at constant precision (Table~\\ref{tab:pr-concept}). The effect is "
      "largest for categories rich in lexical variation (Audience, Cuisine) and smallest "
      "for closed-vocabulary categories (Meal).}")
    a("\\label{tab:coverage-global}"); a("\\end{table}")
    TABLES.mkdir(parents=True,exist_ok=True)
    (TABLES/"coverage_global.tex").write_text("\n".join(L)+"\n")

    # ---- figure: boxplot of miss% per category ----
    IMAGES.mkdir(parents=True,exist_ok=True)
    fig,ax=plt.subplots(figsize=(6.0,3.2))
    order=[d for d in DIMS if bycat[d]]
    data=[[r["miss_pct"] for r in bycat[d]] for d in order]
    bp=ax.boxplot(data, labels=[DISP[d] for d in order], showmeans=True, patch_artist=True,
                  medianprops=dict(color="black"), meanprops=dict(marker="D",markerfacecolor="white",markeredgecolor="black",markersize=4))
    for patch in bp["boxes"]: patch.set_facecolor("#9ecae1"); patch.set_alpha(0.8)
    ax.set_ylabel("recipes missed by exact-word search (%)")
    ax.set_ylim(0,100)
    ax.grid(axis="y",alpha=0.3)
    ax.set_title(f"Coverage gain of SER facets over literal keyword search\n(top-{TOPN} concepts per category)",fontsize=9)
    fig.tight_layout()
    fig.savefig(IMAGES/"coverage_global.pdf"); fig.savefig(IMAGES/"coverage_global.png",dpi=150)
    print(f"Wrote {TABLES/'coverage_global.tex'}, {IMAGES/'coverage_global.pdf'}")

    # ---- console ----
    print(f"\n{'Category':10s} {'#':>3s} {'med miss%':>9s} {'med SER/kw×':>12s}")
    for d in DIMS:
        rs=bycat[d]
        if not rs: continue
        miss=[r["miss_pct"] for r in rs]; mult=[r["v1"]/r["kw"] for r in rs if r["kw"]>0]
        print(f"{DISP[d]:10s} {len(rs):3d} {st.median(miss):8.0f}% {st.median(mult):11.2f}x")
    print(f"\nGlobal median miss%: {st.median(allmiss):.0f}% over {len(per_concept)} concepts")
    # stepwise decomposition (mean share recovered by each step)
    ext=st.mean([r['ext_added_pct'] for r in per_concept]); norm=st.mean([r['norm_added_pct'] for r in per_concept]); kwp=st.mean([100*r['kw']/r['v1'] for r in per_concept])
    print(f"Mean decomposition of the deployed facet set: keyword {kwp:.0f}% | +extraction {ext:.0f}% | +normalization {norm:.0f}%")


if __name__=="__main__":
    main()
