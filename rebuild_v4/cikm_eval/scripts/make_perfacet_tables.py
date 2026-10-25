"""
Per-facet (single-concept) tables. Recipe counts out of 500 (a recipe counts once if
any of its reviews triggers the facet). This is the interpretable, standard per-item
way to show the benefit, instead of summing memberships over the top-20.

Produces:
  tables/perfacet_2stage.tex   concept | plain word search | SER facet | note
  tables/perfacet_4stage.tex   concept | keyword | +gemma | v1 | v2 | note

Stages (recipe counts):
  keyword  recipes whose reviews contain the literal canonical word (plain search)
  gemma    recipes Gemma tagged with that exact entity (pre-normalization)
  v1       round 1 of the skill: merge only high-frequency variants (freq >= 15) + c
  v2       deployed: all variants merged (normalized_entity == c)
"""
import json, re
from collections import defaultdict, Counter
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
TR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/extracted_attributes_500recipes.jsonl")
PR = Path("/Users/liliu/subjective_DB/spn_datasets/food/phase3_llm_extraction/data/processed_attributes_500recipes.jsonl")
ROUND1_T = 15

# representative concepts (dim, canonical, note). garlic = honest ingredient caveat.
# (dim, concept, merge-type, note) -- spans the gradient of merge kinds
CONCEPTS = [
    ("audience_enjoyment","husband","Abbreviation","DH, hubby, hubs"),
    ("audience_enjoyment","kids","Plural / variant","children, kid, toddler, child"),
    ("taste_flavor","tangy","Synonym cluster","tart, zesty, zingy"),
    ("taste_flavor","spicy","Synonym cluster","heat, kick, hot"),
    ("audience_enjoyment","mother","LLM-internal","mom, mum (resolved by Gemma)"),
]

text=defaultdict(list); seen=set()
for line in open(TR):
    r=json.loads(line); rid=r["recipe_id"]; i=r["review_idx"]
    if (rid,i) not in seen: text[rid].append(r["review_text"].lower()); seen.add((rid,i))

gemma=defaultdict(lambda:defaultdict(set))   # dim->entity->recipes
norm=defaultdict(lambda:defaultdict(set))    # dim->normalized->recipes
m2=defaultdict(dict)                         # dim->raw entity->normalized
rawrec=defaultdict(lambda:defaultdict(set))  # dim->raw entity->recipes (for freq)
for line in open(PR):
    r=json.loads(line); rid=r["recipe_id"]
    for a in r["attributes"]:
        d=a["dimension"]; e=(a.get("entity") or "").strip().lower(); ne=(a.get("normalized_entity") or "").strip().lower()
        if not ne: continue
        if e: gemma[d][e].add(rid); m2[d][e]=ne; rawrec[d][e].add(rid)
        norm[d][ne].add(rid)

def litcount(w):
    forms={w, w.replace("-"," "), w.replace("-","")}
    ps=[re.compile(r"\b"+re.escape(f)+r"\b") for f in forms if f]
    return sum(1 for rid,tx in text.items() if any(p.search(t) for t in tx for p in ps))

def stages(d,c):
    kw=litcount(c)
    g=len(gemma[d].get(c,set()))
    variants=[e for e,nrm in m2[d].items() if nrm==c]
    Vc1={e for e in variants if e==c or len(rawrec[d][e])>=ROUND1_T} | {c}
    v1=set()
    for e in Vc1: v1|=rawrec[d].get(e,set())
    v2=len(norm[d].get(c,set()))
    return kw,g,len(v1),v2

def merged_variants(d,c):
    """Which synonym variants get merged at v1 (freq>=T) vs v2 (long tail)."""
    variants=[(e,len(rawrec[d][e])) for e,nrm in m2[d].items() if nrm==c and e!=c]
    v1add=sorted([e for e,n in variants if n>=ROUND1_T], key=lambda e:-len(rawrec[d][e]))
    v2add=sorted([e for e,n in variants if n<ROUND1_T], key=lambda e:-len(rawrec[d][e]))
    return v1add, v2add

# surface words Gemma maps to the concept INTERNALLY (raw entity == c, but the review
# word in source_text differs). Reveals Gemma's own synonym resolution, before our skill.
GEMMA_CAND={
    "husband":["dh","hubby","hubs","hubbie"],
    "kids":["children","kid","kiddos","toddler","child"],
    "potluck":["potlucks","pot luck","pot lucks"],
    "tangy":["tart","tang","zesty","zingy","tartness"],
    "spicy":["heat","kick","hot","fiery"],
    "game-day":["super bowl","football game","game night","game day","game"],
    "mediterranean":["greek"],
    "mother":["mom","mum","mommy","mama","momma"],
}
_SRC=defaultdict(lambda:defaultdict(set))   # dim -> raw entity -> set(source_text)
for _line in open(PR):
    _r=json.loads(_line)
    for _a in _r["attributes"]:
        _SRC[_a["dimension"]][(_a.get("entity") or "").strip().lower()].add((_a.get("source_text") or "").lower())
def gemma_resolved(d,c):
    texts=_SRC[d].get(c,set())
    return [w for w in GEMMA_CAND.get(c,[]) if any(re.search(r"\b"+re.escape(w)+r"\b",t) for t in texts)]

DISP={"taste_flavor":"Flavor","texture_mouthfeel":"Texture","meal_type":"Meal","occasion_holiday":"Occasion","audience_enjoyment":"Audience","cuisine_type":"Cuisine"}
rows=[(DISP[d],mtype,c,note,*stages(d,c)) for d,c,mtype,note in CONCEPTS]

def fmt_syn(lst, k=4):
    if not lst: return "--"
    shown=", ".join(lst[:k])
    return shown + (f", +{len(lst)-k}" if len(lst)>k else "")

# ---- Table 1: 2-stage, grouped by merge type ----
L=[];a=L.append
a("% Auto-generated by scripts/make_perfacet_tables.py")
a("\\begin{table}[t]");a("\\centering");a("\\small");a("\\setlength{\\tabcolsep}{5pt}")
a("\\begin{tabular}{@{}lllrr@{}}")
a("\\toprule")
a("\\textbf{Merge type} & \\textbf{Concept} & \\textbf{merged synonyms} & \\textbf{Plain} & \\textbf{SER} \\\\")
a(" & & & \\textbf{search} & \\textbf{facet} \\\\")
a("\\midrule")
for dim,mtype,c,note,kw,g,v1,v2 in rows:
    a(f"{mtype} & {c} & {note} & {kw} & {v2} \\\\")
a("\\bottomrule");a("\\end{tabular}")
a("\\caption{Per-facet coverage (recipes out of 500), one representative concept per merge type. "
  "\\emph{Plain search}: recipes whose reviews contain the literal canonical word. \\emph{SER facet}: "
  "recipes the normalized facet surfaces (any surface form). All merges shown are clean synonyms. "
  "The gain is largest when the canonical word itself is rarely written (game-day, mediterranean), "
  "where users instead say `super bowl' or `greek'.}")
a("\\label{tab:perfacet-2stage}");a("\\end{table}")
(PAPER/"tables"/"perfacet_2stage.tex").write_text("\n".join(L)+"\n")

# ---- Table 2: 4-stage WITH incremental merged synonyms, grouped by merge type ----
L=[];a=L.append
a("% Auto-generated by scripts/make_perfacet_tables.py")
a("\\begin{table*}[t]");a("\\centering");a("\\small");a("\\setlength{\\tabcolsep}{5pt}")
a("\\begin{tabular}{@{}l rrrr lll@{}}")
a("\\toprule")
a("& \\multicolumn{4}{c}{\\textbf{Recipes found (of 500)}} & \\multicolumn{3}{c}{\\textbf{Synonyms folded in at each stage}} \\\\")
a("\\cmidrule(lr){2-5}\\cmidrule(lr){6-8}")
a("\\textbf{Concept} & \\textbf{Keyword} & \\textbf{+Gemma} & \\textbf{v1} & \\textbf{v2} & \\textbf{Gemma (internal)} & \\textbf{v1 (frequent)} & \\textbf{v2 (long tail)} \\\\")
a("\\midrule")
for dim,mtype,c,note,kw,g,v1,v2 in rows:
    d=[k for k,val in DISP.items() if val==dim][0]
    v1add,v2add=merged_variants(d,c)
    gres=gemma_resolved(d,c)
    a(f"{c} & {kw} & {g} & {v1} & {v2} & {fmt_syn(gres)} & {fmt_syn(v1add)} & {fmt_syn(v2add)} \\\\")
a("\\bottomrule");a("\\end{tabular}")
a("\\caption{Per-facet coverage across the four pipeline stages (recipes out of 500), with the "
  "synonym variants folded in at each stage. \\emph{Keyword} is the literal word; \\emph{+Gemma} the "
  "recipes Gemma tagged; \\emph{v1}/\\emph{v2} after merging the high-frequency and long-tail variants. "
  "+Gemma can fall below Keyword (e.g., spicy, kids) because Gemma skips negated, conditional, or "
  "ingredient mentions (``not spicy'', ``spicy mustard'') that a literal match counts. Counts are recipe "
  "unions, so merging a frequent variant yields one consolidated facet rather than new recipes (hubby with "
  "husband); the gain is largest where the canonical word is rare and its variants form the long tail "
  "(tangy $\\to$ tart/zesty/zingy).}")
a("\\label{tab:perfacet-4stage}");a("\\end{table*}")
(PAPER/"tables"/"perfacet_4stage.tex").write_text("\n".join(L)+"\n")

print("Wrote tables/perfacet_2stage.tex and tables/perfacet_4stage.tex\n")
print(f"{'Type':18s} {'Concept':13s} {'kw':>4s} {'+gem':>5s} {'v1':>4s} {'v2':>4s}  v1 / v2 syns")
for dim,mtype,c,note,kw,g,v1,v2 in rows:
    d=[k for k,val in DISP.items() if val==dim][0]
    v1add,v2add=merged_variants(d,c)
    print(f"{mtype:18s} {c:13s} {kw:4d} {g:5d} {v1:4d} {v2:4d}  [{', '.join(v1add) or '-'}] / [{', '.join(v2add[:3]) or '-'}]")

# ---- Table 3: compact EXAMPLE table (husband + tangy), table-2 format ----
EXAMPLE=[("audience_enjoyment","husband","Abbreviation"),("taste_flavor","tangy","Synonym cluster")]
L=[];a=L.append
a("% Auto-generated by scripts/make_perfacet_tables.py")
a("\\begin{table}[t]");a("\\centering");a("\\small");a("\\setlength{\\tabcolsep}{4pt}")
a("\\begin{tabular}{@{}l rrrr l@{}}")
a("\\toprule")
a("\\textbf{Concept (type)} & \\textbf{KW} & \\textbf{+Gem} & \\textbf{v1} & \\textbf{v2} & \\textbf{Synonyms folded in (stage)} \\\\")
a("\\midrule")
for d,c,mt in EXAMPLE:
    kw,g,v1,v2=stages(d,c)
    v1a,v2a=merged_variants(d,c)
    gres=gemma_resolved(d,c)
    parts=[]
    if gres: parts.append("Gemma: "+", ".join(gres[:4]))
    if v1a: parts.append("v1: "+", ".join(v1a[:4]))
    if v2a: parts.append("v2: "+", ".join(v2a[:4]))
    a(f"{c} ({mt}) & {kw} & {g} & {v1} & {v2} & {'; '.join(parts)} \\\\")
a("\\bottomrule");a("\\end{tabular}")
a("\\caption{Two illustrative facets across the pipeline (recipes of 500). \\emph{husband} "
  "is an abbreviation cluster: Gemma resolves most DH/hubby internally, v1 folds the residual. "
  "\\emph{tangy} is a semantic cluster: Gemma is selective (the bare word can be a negation or "
  "modify a condiment), v1 folds tang/tart, and v2 adds the long tail tartness/zesty/zingy. "
  "Counts are recipe unions, so a frequent variant that co-occurs with the canonical adds few "
  "new recipes; the value is one complete facet.}")
a("\\label{tab:perfacet-example}");a("\\end{table}")
(PAPER/"tables"/"perfacet_example.tex").write_text("\n".join(L)+"\n")
print("\nWrote tables/perfacet_example.tex (husband + tangy)")
