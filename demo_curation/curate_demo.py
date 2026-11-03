"""Hand curation of the deployed demo data (2026-11-02).

The paper's numbers come from the rebuild_v4* pipelines, not from these files, so
curation here only changes what the demo shows. For recipes it touches long-tail
values only: no value among a category's 20 most frequent changes its recipe count,
and the recipe set stays at 500.

Every operation is listed below. Run from the repo root:
    python3 demo_curation/curate_demo.py
Backups: <file>.bak.pre-curation-2026-11-02 (written once, never overwritten).
"""
import json
import os
import shutil

TAG = '.bak.pre-curation-2026-11-02'

RECIPES = {
    'path': 'food-exhibit-data-500recipes.json',
    'fields': {  # item field -> (support field, attribute dimension, min supporting reviews)
        'audience_attributes': ('audience_support', 'audience_enjoyment', 1),
        'occasion_attributes': ('occasion_support', 'occasion_holiday', 1),
        'texture_attributes': ('texture_support', 'texture_mouthfeel', 1),
        'taste_attributes': ('taste_support', 'taste_flavor', 2),
        'meal_type_attributes': ('meal_type_support', 'meal_type', 1),
        'type_attributes': ('type_support', 'cuisine_type', 1),
    },
    'rename': {  # value -> new value, within a field
        'audience_attributes': {'roommates': 'roommate', 'girl': 'girls', "husband's family": 'in-laws'},
        'occasion_attributes': {'camping trip': 'camping', 'graduation party': 'graduation',
                                'sunday': 'sunday dinner', 'bbq': 'BBQ', "valentine's day": "Valentine's Day"},
    },
    'drop': {  # values that are not an audience, occasion, texture or flavor
        'audience_attributes': ['youngest', 'twins', "kids' friends", 'client', "daughter's boyfriend",
                                "friend's daughter", 'vegetarian', 'vegetarians', 'meat lovers'],
        'occasion_attributes': ['friday', 'saturday night'],
        'texture_attributes': ['pink', 'not spread', 'not fall apart', 'not breaking'],
        'taste_attributes': ['comfort food'],
    },
    'drop_item': [],  # (item name contains, field, value)
    'drop_span': [  # (item name contains, field, value, span text contains): weak or unsuitable evidence
        ('Slow-Cooker Cheesy Chicken', 'audience_attributes', 'kids', '3.5 stars'),
        ('Slow-Cooker Cheesy Chicken', 'audience_attributes', 'kids', 'brain damaged'),
        ('Zuppa Toscana', 'texture_attributes', 'velvety', 'I like my soups'),
        ('Zuppa Toscana', 'texture_attributes', 'tender', 'Chard instead of Kale'),
    ],
}

MOVIES = {
    'path': 'movies/movie-exhibit-data-100movies.json',
    'fields': {
        'subjective_feeling': ('subjective_feeling_support', 'Subjective-Feeling', 1),
        'vibe_style': ('vibe_style_support', 'Vibe-Style', 1),
        'plot': ('plot_support', 'Plot', 1),
        'occasion': ('occasion_support', 'Occasion', 1),
        'target_audience': ('target_audience_support', 'Target-Audience', 1),
    },
    'rename': {
        'subjective_feeling': {'amusing': 'funny', 'touching': 'moving'},
    },
    'drop': {
        # Relatives and genders say who the reviewer watched with, not who the film suits.
        'target_audience': ['son', 'husband', 'father', 'daughter', 'women', 'men', 'boys', 'younger audience'],
        'occasion': ['big screen'],
        # Not a style, or already a value in Subjective Feeling or Plot.
        'vibe_style': ['british', 'period', 'special effects', 'action-packed', 'creepy', 'charming', 'disturbing'],
    },
    'drop_item': [
        ('The Fog', 'target_audience', 'kids'),
        ('Mr. & Mrs. Smith', 'target_audience', 'family'),
        ('Downfall', 'subjective_feeling', 'creepy'),
    ],
    'drop_span': [],
}

GAMES = {
    'path': 'games/game-exhibit-data-100games.json',
    'fields': {
        'difficulty_attributes': ('difficulty_support', 'Difficulty-perception', 1),
        'gameplay_attributes': ('gameplay_support', 'Gameplay-experience', 1),
        'activity_attributes': ('activity_support', 'In-game-activity', 1),
        'purpose_attributes': ('purpose_support', 'Play-purpose', 1),
        'player_type_attributes': ('player_type_support', 'Player-type', 1),
        'value_attributes': ('value_support', 'Value-judgment', 1),
    },
    'rename': {
        'value_attributes': {'worth full price': 'worth the price'},
    },
    'drop': {
        'player_type_attributes': ['masochists', 'introverts', 'women', 'cat lovers'],
        'activity_attributes': ['multiple endings', 'magic', 'clicking'],
        # Already values in Gameplay or Activities.
        'difficulty_attributes': ['simple', 'complex'],
        'gameplay_attributes': ['teamwork'],
    },
    'drop_item': [
        ('Cookie Clicker', 'gameplay_attributes', 'engaging'),  # mock-serious review
        ('Cookie Clicker', 'gameplay_attributes', 'deep'),
        ('Hell Let Loose', 'difficulty_attributes', 'hard'),  # from "more hardcore"
        ('Helltaker', 'value_attributes', 'worth the price'),  # free game
        ('Poppy Playtime', 'value_attributes', 'worth the price'),  # free game
    ],
    'drop_span': [],
}


def attr_value(a):
    return a.get('normalized_entity') or a.get('normalized_attribute') or a.get('entity') or a.get('attribute') or ''


def set_attr_value(a, v):
    key = 'normalized_entity' if 'normalized_entity' in a or 'dimension' in a else 'normalized_attribute'
    a[key] = v


def attr_dim(a):
    return a.get('dimension') or a.get('category')


def span_text(a, text):
    if isinstance(a.get('span'), dict):
        return text[a['span']['start']:a['span']['end']]
    if a.get('span_start') is not None:
        return text[a['span_start']:a['span_end']]
    return a.get('span') or ''


def curate(cfg, log):
    path = cfg['path']
    if not os.path.exists(path + TAG):
        shutil.copy(path, path + TAG)
    data = json.load(open(path + TAG))  # always start from the pre-curation snapshot
    dim_of = {f: v[1] for f, v in cfg['fields'].items()}

    for it in data['items']:
        name = it.get('name', '')
        for field, (sup_field, dim, min_sup) in cfg['fields'].items():
            vals = list(it.get(field) or [])
            sup = dict(it.get(sup_field) or {})
            for old, new in cfg['rename'].get(field, {}).items():
                if old in vals:
                    vals = [new if v == old else v for v in vals]
                    sup[new] = sup.get(new, 0) + sup.pop(old, 0)
                    log.append(f'{path}: {name}: {field} {old} -> {new}')
                for r in it.get('reviews', []):
                    for a in r.get('attributes', []):
                        if attr_dim(a) == dim and attr_value(a) == old:
                            set_attr_value(a, new)
            for v in cfg['drop'].get(field, []):
                if v in vals:
                    vals.remove(v)
                    sup.pop(v, None)
                    log.append(f'{path}: {name}: {field} drop {v}')
            for frag, f, v in cfg['drop_item']:
                if f == field and frag in name and v in vals:
                    vals.remove(v)
                    sup.pop(v, None)
                    log.append(f'{path}: {name}: {field} drop {v} (item)')
            for frag, f, v, span_frag in cfg['drop_span']:
                if f != field or frag not in name:
                    continue
                for r in it.get('reviews', []):
                    keep = []
                    for a in r.get('attributes', []):
                        if attr_dim(a) == dim and attr_value(a) == v and span_frag in span_text(a, r['review_text']):
                            sup[v] = sup.get(v, 0) - 1
                            log.append(f'{path}: {name}: {field} drop span "{span_text(a, r["review_text"])[:50]}"')
                        else:
                            keep.append(a)
                    r['attributes'] = keep
                if v in vals and sup.get(v, 0) < min_sup:
                    vals.remove(v)
                    sup.pop(v, None)
                    log.append(f'{path}: {name}: {field} drop {v} (support below {min_sup})')
            seen = []
            for v in vals:
                if v not in seen:
                    seen.append(v)
            it[field] = sorted(seen, key=str.lower)
            if sup_field in it:
                it[sup_field] = sup
        # The card count is the number of review facet values the item shows.
        it['subjective_attribute_count'] = sum(len(it.get(f) or []) for f in cfg['fields'])
        if 'subjective_attributes' in it:
            union = []
            for f in cfg['fields']:
                for v in it.get(f) or []:
                    if v not in union:
                        union.append(v)
            it['subjective_attributes'] = union
    json.dump(data, open(path, 'w'), ensure_ascii=False)
    return data


if __name__ == '__main__':
    log = []
    for cfg in (RECIPES, MOVIES, GAMES):
        curate(cfg, log)
    os.makedirs('demo_curation', exist_ok=True)
    open('demo_curation/curation_log.txt', 'w').write('\n'.join(log) + '\n')
    print(len(log), 'operations; log in demo_curation/curation_log.txt')
