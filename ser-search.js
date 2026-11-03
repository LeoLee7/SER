// ---------------------------------------------------------------------
// SER shared query routing, used by the recipe, movie and game pages.
//
// Each page provides:
//   * loadExhibitData()          -> Promise of the Exhibit JSON ({items: [...]})
//   * window.SER_SEARCH_CONFIG   -> { domainStopWords: [...], facetFields?: [...] }
//     facetFields defaults to every non-NumericRange facet expression on the page.
//     querySynonyms maps a word users type to the value it names
//     ({ spooky: 'creepy' }), for variants that were merged into a value.
//
// Two problems the old search had, both visible in the CIKM review:
//   1. Query terms that matched no facet value were silently dropped.
//   2. Facet values differ enormously in how much they narrow the corpus.
//      audience:self covers 97% of recipes. Selecting such a value filters
//      almost nothing, so the result set was driven by whatever term happened
//      to survive.
// So each query term is routed rather than forced onto a facet, and a facet
// value filters only when it is discriminative. Common values are held and
// applied alongside a discriminative constraint, or on their own when the
// query has none. Unmatched terms are reported in the status line.
// ---------------------------------------------------------------------

// A facet value present in more than this share of the corpus is kept for
// browsing but is not used on its own to filter an auto-parsed query.
const FACET_DF_CEILING = 0.40;

const SER_BASE_STOP_WORDS = [
  'for', 'my', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'of',
  'with', 'from', 'by', 'about', 'as', 'into', 'through', 'during', 'before',
  'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then',
  'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'both', 'each',
  'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same', 'so',
  'than', 'very', 'can', 'will', 'just', 'should', 'now', 'i', 'me', 'something',
  'anything', 'want', 'need', 'looking', 'like', 'that', 'is', 'are', 'be'
];

// Words that are part of a value ("not too hard", "great soundtrack") but say
// nothing on their own. They match only inside a whole phrase.
const SER_NO_SOLO_WORDS = new Set([
  'not', 'no', 'too', 'great', 'good', 'best', 'top', 'really', 'nice', 'super',
  'very', 'lot', 'well', 'rated', 'new', 'old', 'big', 'little', 'day', 'night', 'time'
]);
const SER_NEGATIONS = new Set(['not', 'no', 'without', 'non', 'never']);

let queryIndex = null;

function serConfig() {
  return window.SER_SEARCH_CONFIG || {};
}

// Facet field names, read from the page unless the config lists them.
function serFacetFields() {
  const cfg = serConfig();
  if (cfg.facetFields) return cfg.facetFields;
  const fields = [];
  document.querySelectorAll('[data-ex-role="facet"]').forEach(div => {
    const expr = div.getAttribute('data-ex-expression') || '';
    if (!expr || div.getAttribute('data-ex-facet-class') === 'NumericRange') return;
    const f = expr.replace(/^\./, '');
    if (!fields.includes(f)) fields.push(f);
  });
  return fields;
}

function facetCategory(field) {
  return field.replace(/^\./, '').replace('_attributes', '');
}

function buildQueryIndex(data) {
  if (queryIndex) return queryIndex;
  if (!data || !data.items) return null;

  const items = data.items;
  const n = items.length;
  const facetDF = {};       // "category::value" -> document frequency

  serFacetFields().forEach(field => {
    const cat = facetCategory(field);
    items.forEach(item => {
      let vals = item[field];
      if (vals == null) return;
      if (!Array.isArray(vals)) vals = [vals];
      new Set(vals.map(v => String(v).toLowerCase())).forEach(v => {
        const key = cat + '::' + v;
        facetDF[key] = (facetDF[key] || 0) + 1;
      });
    });
  });

  queryIndex = { n: n, facetDF: facetDF };
  console.log('Query index: ' + n + ' items, ' +
              Object.keys(facetDF).length + ' facet values');
  return queryIndex;
}

// Share of the corpus carrying this facet value. 1 when unknown, which
// makes an unknown value non-discriminative and therefore not a filter.
function facetValueShare(category, value) {
  if (!queryIndex) return 1;
  const df = queryIndex.facetDF[category + '::' + String(value).toLowerCase()];
  return df == null ? 1 : df / queryIndex.n;
}

// Show what the query selected, read back from the facets after the clicks,
// so the line never claims a value that could not be applied.
function facetLabel(facetDiv) {
  return (facetDiv.getAttribute('data-ex-facet-label') ||
          facetDiv.querySelector('.exhibit-facet-header-title')?.textContent || '').trim();
}

function reportSearchRouting(routed, droppedTerms) {
  const termsDisplay = document.getElementById('searchTermsDisplay');
  if (!termsDisplay) return;
  const parts = [];
  const applied = new Set();
  document.querySelectorAll('[data-ex-role="facet"]').forEach(facet => {
    const vals = Array.from(facet.querySelectorAll('.exhibit-facet-value-selected'))
      .map(v => v.getAttribute('title')).filter(Boolean);
    vals.forEach(v => applied.add(v.toLowerCase()));
    if (vals.length > 0) parts.push(vals.join(' or ') + ' (' + facetLabel(facet) + ')');
  });
  const notApplied = routed.filter(m => !applied.has(m.valueLower)).map(m => m.value);
  let text = parts.length > 0 ? parts.join(', ')
    : 'no facet value matches this query, so all items are shown';
  if (notApplied.length > 0) text += '. Not applied, as no item also matches the rest: ' + notApplied.join(', ');
  if (droppedTerms.length > 0) text += '. Not understood: ' + droppedTerms.join(', ');
  termsDisplay.textContent = text;
}

function buildFacetIndex() {
  const index = [];
  document.querySelectorAll('[data-ex-role="facet"]').forEach(facetDiv => {
    const expression = facetDiv.getAttribute('data-ex-expression') || '';
    const facetClass = facetDiv.getAttribute('data-ex-facet-class');
    if (!expression || facetClass === 'NumericRange') return;

    const category = facetCategory(expression);
    // Only value rows: their count is a separate element, and indexing it made
    // a query for "$10" select whichever value 10 items carry.
    facetDiv.querySelectorAll('.exhibit-facet-value').forEach(elem => {
      const value = (elem.getAttribute('title') || '').trim();
      if (!value) return;
      index.push({ category: category, value: value, valueLower: value.toLowerCase(), element: elem });
    });
  });
  return index;
}

// A term that names a value in several facets selects one of them, since
// facets combine with AND. Catalog facets listed in preferFields win (identity
// comes from the catalog); otherwise the value carried by the most items wins.
function pickOneFacet(matches) {
  if (matches.length === 1) return matches[0];
  const prefer = (serConfig().preferFields || []).map(facetCategory);
  const preferred = matches.filter(m => prefer.includes(m.category));
  const pool = preferred.length > 0 ? preferred : matches;
  return pool.slice().sort((a, b) =>
    facetValueShare(b.category, b.value) - facetValueShare(a.category, a.value))[0];
}

// Priority: exact match > starts-with > whole-word match inside a value.
function findBestMatch(term, facetIndex) {
  const termLower = term.toLowerCase();
  const exactMatches = [];
  const startsWithMatches = [];
  const containsMatches = [];

  facetIndex.forEach(entry => {
    if (entry.valueLower === termLower) {
      exactMatches.push(entry);
    } else if (entry.valueLower.startsWith(termLower + ' ') || entry.valueLower.startsWith(termLower + '-')) {
      startsWithMatches.push(entry);
    } else if (entry.valueLower.includes(termLower)) {
      containsMatches.push(entry);
    }
  });

  if (exactMatches.length > 0) return [pickOneFacet(exactMatches)];

  if (startsWithMatches.length > 0) {
    startsWithMatches.sort((a, b) => a.value.length - b.value.length);
    return [startsWithMatches[0]];
  }

  const wholeWordMatches = containsMatches.filter(entry => {
    const regex = new RegExp('\\b' + termLower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b');
    return regex.test(entry.valueLower);
  });
  if (wholeWordMatches.length > 0) {
    wholeWordMatches.sort((a, b) => a.value.length - b.value.length);
    return [wholeWordMatches[0]];
  }
  return [];
}

// Singular forms of a plural word (families -> family, eaters -> eater).
function singularForms(word) {
  if (word.length < 4 || /ss$/.test(word)) return [];
  const forms = [];
  if (/ies$/.test(word)) forms.push(word.replace(/ies$/, 'y'));
  if (/es$/.test(word)) forms.push(word.replace(/es$/, ''));
  if (/s$/.test(word)) forms.push(word.replace(/s$/, ''));
  return forms.filter((f, i, a) => f.length >= 3 && a.indexOf(f) === i);
}

// The phrase itself, then with its last word made singular.
// A page synonym comes first, since it names the value the variant was merged into.
function phraseForms(phrase) {
  const syn = serConfig().querySynonyms || {};
  const words = phrase.split(' ');
  const last = words.pop();
  const forms = [phrase].concat(singularForms(last).map(f => words.concat([f]).join(' ')));
  const named = forms.filter(f => syn[f]).map(f => syn[f].toLowerCase());
  return named.concat(forms);
}

function adjectiveStems(term) {
  if (!/y$/.test(term) || term.length < 5) return [];
  return [term.replace(/ky$/, ''), term.replace(/y$/, 'e'), term.replace(/y$/, '')]
    .filter((s, i, a) => s !== term && s.length >= 4 && a.indexOf(s) === i);
}

// Clicking a value's link selects only that value; clicking its checkbox adds
// it. Use the checkbox when the facet already has a selection, so a second
// term routed to the same facet does not replace the first.
function clickFacetEntry(entry) {
  const facet = entry.element.closest('[data-ex-role="facet"]');
  const hasSelection = facet && facet.querySelector('.exhibit-facet-value-selected');
  const box = entry.element.querySelector('.exhibit-facet-value-checkbox');
  const link = entry.element.querySelector('a');
  if (hasSelection && box) box.click();
  else if (link) link.click();
  else entry.element.click();
}

function performSmartSearch() {
  const searchBox = document.getElementById('customSearchBox');
  if (!searchBox) return;

  const query = searchBox.value.trim();
  if (!query) { clearSearch(); return; }

  const stopWords = new Set(SER_BASE_STOP_WORDS.concat(serConfig().domainStopWords || []));
  let normalized = query.toLowerCase().replace(/['’]/g, "'");
  (serConfig().queryRewrites || []).forEach(([pattern, to]) => {
    normalized = normalized.replace(new RegExp(pattern, 'g'), to);
  });
  const words = normalized.split(/\s+/)
    .map(w => w.replace(/'s$/, '').replace(/[^a-z0-9-]/g, ''));
  const searchTerms = words.filter(word => word.length > 1 && !stopWords.has(word));
  // A word after "not" is the opposite of what the user wants unless a value
  // names the whole phrase ("not too sweet"), so it is never routed alone.
  const negated = new Set(words.filter((w, i) => i > 0 && SER_NEGATIONS.has(words[i - 1])));
  if (searchTerms.length === 0) { clearSearch(); return; }

  const statusDiv = document.getElementById('searchStatus');
  const termsDisplay = document.getElementById('searchTermsDisplay');
  if (statusDiv && termsDisplay) {
    termsDisplay.textContent = '...';
    statusDiv.classList.add('active');
  }

  clearAllFacetSelections();

  loadExhibitData().then(data => {
    buildQueryIndex(data);
    setTimeout(() => {
      const facetIndex = buildFacetIndex();

      // A phrase that names a value exactly goes first, longest first, so its
      // words are not routed one by one ([horror fans] must not also select
      // "fans of the book"). Then single words, then the other phrases.
      const phrases = [];
      for (let len = searchTerms.length; len >= 2; len--) {
        for (let i = 0; i <= searchTerms.length - len; i++) {
          phrases.push(searchTerms.slice(i, i + len).join(' '));
        }
      }
      const namesValue = p => phraseForms(p).some(f => facetIndex.some(e => e.valueLower === f));
      const allTermCombinations = phrases.filter(namesValue)
        .concat(searchTerms, phrases.filter(p => !namesValue(p)).reverse());

      const toClick = [];
      const matchedTerms = new Set();
      const droppedTerms = [];
      const weakMatches = [];

      allTermCombinations.forEach(phrase => {
        const phraseWords = phrase.split(' ');
        if (phraseWords.every(w => matchedTerms.has(w))) return;
        if (phraseWords.length === 1 && (SER_NO_SOLO_WORDS.has(phrase) || negated.has(phrase))) {
          if (!SER_NO_SOLO_WORDS.has(phrase)) droppedTerms.push('not ' + phrase);
          return;
        }

        let matches = [];
        for (const form of phraseForms(phrase)) {
          matches = findBestMatch(form, facetIndex);
          if (matches.length > 0) break;
        }
        // An adjective with no value of its own tries its noun stem
        // (garlicky -> garlic, cheesy -> cheese).
        if (matches.length === 0 && phraseWords.length === 1) {
          for (const stem of adjectiveStems(phrase)) {
            matches = findBestMatch(stem, facetIndex);
            if (matches.length > 0) break;
          }
        }
        const useful = matches.filter(m =>
          facetValueShare(m.category, m.value) <= FACET_DF_CEILING);

        if (useful.length > 0) {
          useful.forEach(match => {
            if (!toClick.some(tc => tc.category === match.category &&
                                    tc.valueLower === match.valueLower)) {
              toClick.push(match);
              console.log(`Route "${phrase}" → facet [${match.category}] "${match.value}" ` +
                          `(${(facetValueShare(match.category, match.value) * 100).toFixed(0)}% of corpus)`);
            }
          });
          phraseWords.forEach(w => matchedTerms.add(w));
          return;
        }

        // Single words only from here: a dropped phrase says nothing new.
        if (phraseWords.length > 1) return;

        if (matches.length > 0) {
          // Too common to carry the query alone. Hold it and apply it only if
          // a discriminative constraint also survives.
          const m = matches[0];
          console.log(`Route "${phrase}" → weak facet [${m.category}] "${m.value}" ` +
                      `(${(facetValueShare(m.category, m.value) * 100).toFixed(0)}% of corpus), held`);
          if (!weakMatches.some(w => w.category === m.category &&
                                     w.valueLower === m.valueLower)) weakMatches.push(m);
          matchedTerms.add(phrase);
          return;
        }

        droppedTerms.push(phrase);
      });

      // Held values join a discriminative constraint. With none, they are still
      // the user's words, so they apply on their own ([fun multiplayer game]).
      weakMatches.forEach(m => {
        if (!toClick.some(tc => tc.category === m.category &&
                                tc.valueLower === m.valueLower)) toClick.push(m);
        console.log(`Applying held facet [${m.category}] "${m.value}"`);
      });

      if (droppedTerms.length > 0) console.log('No match anywhere for: ' + droppedTerms.join(', '));

      // Click sequentially: each click re-renders the facets.
      function clickSequentially(items, idx) {
        if (idx >= items.length) { setTimeout(() => reportSearchRouting(items, droppedTerms), 700); return; }
        const match = items[idx];
        const fresh = buildFacetIndex().find(e =>
          e.category === match.category && e.valueLower === match.valueLower);
        if (fresh && !fresh.element.classList.contains('exhibit-facet-value-selected')) {
          clickFacetEntry(fresh);
          console.log('Clicked:', match.value, 'in', match.category);
        }
        setTimeout(() => clickSequentially(items, idx + 1), 200);
      }
      clickSequentially(toClick, 0);

      // Retry discriminative matches for unmatched terms in case Exhibit had
      // not finished rendering the facet lists.
      const unmatchedTerms = searchTerms.filter(t => !matchedTerms.has(t) &&
        !SER_NO_SOLO_WORDS.has(t) && !negated.has(t));
      if (unmatchedTerms.length > 0) {
        setTimeout(() => {
          const freshIndex = buildFacetIndex();
          unmatchedTerms.forEach(term => {
            findBestMatch(term, freshIndex)
              .filter(m => facetValueShare(m.category, m.value) <= FACET_DF_CEILING)
              .forEach(match => {
                if (!match.element.classList.contains('exhibit-facet-value-selected')) {
                  clickFacetEntry(match);
                  console.log(`Search retry: "${term}" → [${match.category}] "${match.value}"`);
                }
              });
          });
        }, 500);
      }
    }, 300);
  });
}

// Deselect by clicking the anchor Exhibit binds its handler to, not the
// wrapper. Clicking the wrapper silently does nothing, which is how
// selections used to leak across queries.
function clearAllFacetSelections() {
  let guard = 0;
  while (guard++ < 20) {
    const selected = document.querySelector('.exhibit-facet-value-selected');
    if (!selected) break;
    const link = selected.querySelector('a');
    if (link) link.click(); else selected.click();
    if (document.querySelector('.exhibit-facet-value-selected') === selected) {
      selected.classList.remove('exhibit-facet-value-selected');
    }
  }
}

function clearSearch() {
  const searchBox = document.getElementById('customSearchBox');
  if (searchBox) { searchBox.value = ''; searchBox.focus(); }
  clearAllFacetSelections();
  const statusDiv = document.getElementById('searchStatus');
  if (statusDiv) statusDiv.classList.remove('active');
}

function initializeCustomSearch() {
  const searchBox = document.getElementById('customSearchBox');
  if (!searchBox || searchBox.dataset.serBound) return;
  searchBox.dataset.serBound = '1';
  searchBox.addEventListener('keypress', e => { if (e.key === 'Enter') performSmartSearch(); });
  searchBox.addEventListener('keydown', e => { if (e.key === 'Escape') clearSearch(); });
}
