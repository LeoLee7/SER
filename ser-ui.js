// ---------------------------------------------------------------------
// SER shared review modal helpers, used by the recipe, movie and game pages.
//
// Each page provides window.SER_UI_CONFIG:
//   reviewFields: { <item field>: { label: 'Audience', dims: [<attribute dimension>, ...] } }
// Only these facets filter the review modal; catalog facets (cuisine,
// cast, price) have no review evidence and must not empty it.
// ---------------------------------------------------------------------

function serUiConfig() {
  return window.SER_UI_CONFIG || { reviewFields: {} };
}

// Attribute dimension -> item field, built once from the config.
let serDimToField = null;
function serFieldForDim(dim) {
  if (!serDimToField) {
    serDimToField = {};
    const fields = serUiConfig().reviewFields;
    Object.keys(fields).forEach(f => fields[f].dims.forEach(d => { serDimToField[d] = f; }));
  }
  return serDimToField[dim];
}

// Values selected in review facets, as [{field, label, value}].
function serSelectedReviewValues() {
  const fields = serUiConfig().reviewFields;
  const out = [];
  document.querySelectorAll('[data-ex-role="facet"]').forEach(facet => {
    const field = (facet.getAttribute('data-ex-expression') || '').replace(/^\./, '');
    if (!fields[field]) return;
    facet.querySelectorAll('.exhibit-facet-value-selected').forEach(v => {
      const value = (v.getAttribute('title') || v.querySelector('.exhibit-facet-value-link')?.textContent || '').trim();
      if (value && !out.some(o => o.field === field && o.value === value)) {
        out.push({ field: field, label: fields[field].label, value: value });
      }
    });
  });
  return out;
}

// The three datasets store spans differently; return {start, end, field, value}.
function serReadAttribute(attr, text) {
  const dim = attr.dimension || attr.category || '';
  const field = serFieldForDim(dim);
  const value = (attr.normalized_entity || attr.normalized_attribute || attr.entity || attr.attribute || '').trim();
  let start, end;
  if (attr.span && typeof attr.span === 'object') { start = attr.span.start; end = attr.span.end; }
  else if (attr.span_start != null) { start = attr.span_start; end = attr.span_end; }
  else if (typeof attr.span === 'string') { start = text.indexOf(attr.span); end = start + attr.span.length; }
  if (!field || !value || start == null || start < 0 || end > text.length || start >= end) return null;
  return { start: start, end: end, field: field, value: value };
}

// Review text arrives with HTML entities and <br/> tags from the source sites.
const serDecoder = document.createElement('textarea');
function serCleanText(raw) {
  // Some reviews are encoded twice (&amp;#039;), so decode until stable.
  let text = raw;
  for (let i = 0; i < 3; i++) {
    serDecoder.innerHTML = text.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '');
    if (serDecoder.value === text) break;
    text = serDecoder.value;
  }
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML.replace(/\n+/g, '<br>');
}

// Highlight the spans behind the values this item carries. With a selection,
// only the selected values are highlighted and counted. Overlapping spans
// merge into one highlight whose tooltip lists every value.
function serRenderReview(item, review, selected) {
  const text = review.review_text || '';
  const fields = serUiConfig().reviewFields;
  const carried = v => (item[v.field] || []).some(x => String(x).toLowerCase() === v.value.toLowerCase());
  const isSelected = v => selected.some(s => s.field === v.field && s.value.toLowerCase() === v.value.toLowerCase());

  const spans = [];
  (review.attributes || []).forEach(attr => {
    const a = serReadAttribute(attr, text);
    if (!a || !carried(a)) return;
    if (selected.length > 0 && !isSelected(a)) return;
    spans.push(a);
  });
  spans.sort((x, y) => x.start - y.start || y.end - x.end);

  const groups = [];
  spans.forEach(s => {
    const last = groups[groups.length - 1];
    if (last && s.start < last.end) {
      last.end = Math.max(last.end, s.end);
      last.items.push(s);
    } else {
      groups.push({ start: s.start, end: s.end, items: [s] });
    }
  });

  let html = '';
  let pos = 0;
  groups.forEach(g => {
    html += serCleanText(text.substring(pos, g.start));
    const tips = [];
    g.items.forEach(s => {
      const tip = fields[s.field].label + ': ' + s.value;
      if (!tips.includes(tip)) tips.push(tip);
    });
    html += '<span class="highlight hl-' + (fields[g.items[0].field].cls || g.items[0].field) +
            '" title="' + tips.join('; ').replace(/"/g, '&quot;') + '">' +
            serCleanText(text.substring(g.start, g.end)) + '</span>';
    pos = g.end;
  });
  html += serCleanText(text.substring(pos));

  const values = new Set(spans.map(s => s.field + '::' + s.value.toLowerCase()));
  return { html: html, spanCount: spans.length, matchCount: selected.length > 0 ? values.size : 0 };
}

// Fill #modalTitle and #modalReviews for one item and open #reviewModal.
function serShowReviews(item) {
  const selected = serSelectedReviewValues();
  let title = 'Reviews for: ' + serDecodeName(item.label || item.name);
  if (selected.length > 0) title += ' (showing reviews that mention: ' + selected.map(s => s.value).join(', ') + ')';
  document.getElementById('modalTitle').textContent = title;

  let rendered = (item.reviews || []).map(r => serRenderReview(item, r, selected));
  if (selected.length > 0) rendered = rendered.filter(r => r.matchCount > 0);
  // Reviews with evidence first, so the modal never opens on an unmarked review.
  rendered.sort((a, b) => b.matchCount - a.matchCount || b.spanCount - a.spanCount);

  let html = '';
  if (rendered.length === 0) {
    html = '<p>No review of this item mentions the selected values.</p>';
  } else {
    rendered.forEach(r => {
      const badge = r.matchCount > 0
        ? '<span class="match-badge">mentions ' + r.matchCount + ' selected value' + (r.matchCount > 1 ? 's' : '') + '</span>'
        : '';
      html += '<div class="review-item"' + (r.matchCount > 0 ? ' style="border-left-width: 5px;"' : '') + '>' +
              badge + '<div class="review-text">' + r.html + '</div></div>';
    });
  }
  document.getElementById('modalReviews').innerHTML = html;
  const body = document.querySelector('#reviewModal .modal-content');
  if (body) body.scrollTop = 0;
  document.getElementById('reviewModal').style.display = 'block';
}

function serDecodeName(name) {
  serDecoder.innerHTML = String(name || '');
  return serDecoder.value;
}

// Facets whose values have a natural order keep it after every re-render.
function serReorderFacet(expression, order) {
  document.querySelectorAll('[data-ex-role="facet"][data-ex-expression="' + expression + '"]').forEach(facet => {
    const values = Array.from(facet.querySelectorAll('.exhibit-facet-value'));
    if (values.length === 0) return;
    const container = values[0].parentElement;
    const current = values.map(v => v.getAttribute('title'));
    const wanted = order.filter(o => current.includes(o));
    if (current.filter(c => order.includes(c)).join('|') === wanted.join('|')) return;
    wanted.forEach(o => container.appendChild(values[current.indexOf(o)]));
  });
}

// Exhibit re-renders facets and pages on every click; reapply page fixes then.
function serOnRender(fn) {
  let pending = false;
  const run = () => { pending = false; fn(); };
  new MutationObserver(() => {
    if (!pending) { pending = true; setTimeout(run, 50); }
  }).observe(document.body, { childList: true, subtree: true });
  setTimeout(fn, 1500);
}

// Exhibit's own "Reset All Filters" link also clears the typed query.
document.addEventListener('click', e => {
  const link = e.target.closest && e.target.closest('a');
  if (link && /reset all filters/i.test(link.textContent)) {
    const box = document.getElementById('customSearchBox');
    if (box) box.value = '';
    const status = document.getElementById('searchStatus');
    if (status) status.classList.remove('active');
  }
}, true);
