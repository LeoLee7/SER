// ---------------------------------------------------------------------
// SER shared query routing, used by the recipe, movie and game pages.
//
// Each page provides:
//   * loadExhibitData()          -> Promise of the Exhibit JSON ({items: [...]})
//   * window.SER_SEARCH_CONFIG   -> { domainStopWords: [...], facetFields?: [...] }
//     facetFields defaults to every non-NumericRange facet expression on the page.
//
// Two problems the old search had, both visible in the CIKM review:
//   1. Query terms that matched no facet value were silently dropped.
//   2. Facet values differ enormously in how much they narrow the corpus.
//      audience:self covers 97% of recipes. Selecting such a value filters
//      almost nothing, so the result set was driven by whatever term happened
//      to survive.
// So each query term is routed rather than forced onto a facet, and a facet
// value filters only when it is discriminative. Common values are held and
// applied only alongside a discriminative constraint. Unmatched terms are
// reported in the status line.
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
  'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now', 'i', 'me'
];

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

// Show the user where each term went.
function reportSearchRouting(facetMatches, droppedTerms) {
  const termsDisplay = document.getElementById('searchTermsDisplay');
  if (!termsDisplay) return;

  const parts = [];
  facetMatches.forEach(m => parts.push(m.value + ' (' + m.category + ')'));
  if (parts.length === 0) parts.push('nothing matched');
  let text = parts.join(', ');
  if (droppedTerms.length > 0) text += '  |  ignored: ' + droppedTerms.join(', ');
  termsDisplay.textContent = text;
}

function buildFacetIndex() {
  const index = [];
  document.querySelectorAll('[data-ex-role="facet"]').forEach(facetDiv => {
    const expression = facetDiv.getAttribute('data-ex-expression') || '';
    const facetClass = facetDiv.getAttribute('data-ex-facet-class');
    if (!expression || facetClass === 'NumericRange') return;

    const category = facetCategory(expression);
    const values = facetDiv.querySelectorAll('.exhibit-facet-value, div[class*="facet-value"]');
    const seen = new Set();
    values.forEach(elem => {
      if (seen.has(elem)) return;
      seen.add(elem);
      // Facet values look like "134 Christmas": strip the leading count.
      const rawText = elem.textContent.trim();
      const value = rawText.replace(/^\d+\s+/, '').replace(/\s*\(\d+\)\s*$/, '').trim();
      if (!value || value.includes('missing')) return;
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

function adjectiveStems(term) {
  if (!/y$/.test(term) || term.length < 5) return [];
  return [term.replace(/ky$/, ''), term.replace(/y$/, 'e'), term.replace(/y$/, '')]
    .filter((s, i, a) => s !== term && s.length >= 4 && a.indexOf(s) === i);
}

function clickFacetEntry(entry) {
  const link = entry.element.querySelector('a');
  if (link) link.click(); else entry.element.click();
}

function performSmartSearch() {
  const searchBox = document.getElementById('customSearchBox');
  if (!searchBox) return;

  const query = searchBox.value.trim();
  if (!query) { clearSearch(); return; }

  const stopWords = new Set(SER_BASE_STOP_WORDS.concat(serConfig().domainStopWords || []));
  const words = query.toLowerCase().replace(/['’]/g, "'").split(/\s+/)
    .map(w => w.replace(/'s$/, '').replace(/[^a-z0-9-]/g, ''));
  const searchTerms = words.filter(word => word.length > 1 && !stopWords.has(word));
  if (searchTerms.length === 0) return;

  const statusDiv = document.getElementById('searchStatus');
  const termsDisplay = document.getElementById('searchTermsDisplay');
  if (statusDiv && termsDisplay) {
    termsDisplay.textContent = searchTerms.join(', ');
    statusDiv.classList.add('active');
  }

  clearAllFacetSelections();

  loadExhibitData().then(data => {
    buildQueryIndex(data);
    setTimeout(() => {
      const facetIndex = buildFacetIndex();

      // Single words first, then multi-word phrases for still-unmatched terms.
      const allTermCombinations = searchTerms.slice();
      for (let len = 2; len <= searchTerms.length; len++) {
        for (let i = 0; i <= searchTerms.length - len; i++) {
          allTermCombinations.push(searchTerms.slice(i, i + len).join(' '));
        }
      }

      const toClick = [];
      const matchedTerms = new Set();
      const droppedTerms = [];
      const weakMatches = [];

      allTermCombinations.forEach(phrase => {
        const phraseWords = phrase.split(' ');
        if (phraseWords.every(w => matchedTerms.has(w))) return;

        let matches = findBestMatch(phrase, facetIndex);
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

      if (toClick.length > 0) {
        weakMatches.forEach(m => {
          if (!toClick.some(tc => tc.category === m.category &&
                                  tc.valueLower === m.valueLower)) toClick.push(m);
          console.log(`Applying held facet [${m.category}] "${m.value}"`);
        });
      } else {
        weakMatches.forEach(m => droppedTerms.push(m.value));
      }

      if (droppedTerms.length > 0) console.log('No match anywhere for: ' + droppedTerms.join(', '));
      reportSearchRouting(toClick, droppedTerms);

      // Click sequentially: each click re-renders the facets.
      function clickSequentially(items, idx) {
        if (idx >= items.length) return;
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
      const unmatchedTerms = searchTerms.filter(t => !matchedTerms.has(t));
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
