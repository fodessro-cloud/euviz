// FINILA insider trades: managers' transactions (MAR art. 19) from js/insiders.json,
// built every hour by scripts/data/insiders_se.py.

const PAGE = 50;
let TRADES = [], META = {};
let page = 1, query = '', sortKey = 'published', sortDir = -1;
const filters = {};

const isNum = v => typeof v === 'number' && isFinite(v);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (v, d = 0) => isNum(v) ? v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';
const eur = v => !isNum(v) ? '—' : v >= 1e6 ? `€${num(v / 1e6, 1)}M` : v >= 1e3 ? `€${num(v / 1e3, 0)}k` : `€${num(v)}`;

// Plain buy / sell for open-market share trades; everything else (options, gifts, subscriptions) is "other".
const SIDE = { Acquisition: 'buy', Disposal: 'sell' };
const side = t => (t.instrumentType === 'Share' && SIDE[t.nature]) || 'other';
const sideCell = t => {
  const s = side(t);
  return s === 'buy' ? '<span class="pos">Buy</span>' : s === 'sell' ? '<span class="neg">Sell</span>' : esc(t.nature);
};
const daysAgo = d => (Date.now() - new Date(d).getTime()) / 864e5;

const COLUMNS = [
  { key: 'published', label: 'Published', left: true, fmt: t => esc(t.published) },
  { key: 'issuer', label: 'Company', left: true, fmt: t => `<span class="company-name">${esc(t.issuer)}</span>` },
  { key: 'person', label: 'Person', left: true, fmt: t => `<span class="company-name">${esc(t.person)}${t.associated === 'Yes' ? ' <span class="ins-note">(related)</span>' : ''}</span>` },
  { key: 'position', label: 'Position', left: true, fmt: t => `<span class="company-name">${esc(shortPosition(t.position))}</span>` },
  { key: 'nature', label: 'Trade', left: true, fmt: sideCell },
  { key: 'instrumentType', label: 'Instrument', left: true, fmt: t => esc(t.instrumentType) },
  { key: 'volume', label: 'Quantity', fmt: t => num(t.volume) },
  { key: 'price', label: 'Price', fmt: t => isNum(t.price) ? `${num(t.price, 2)} ${esc(t.currency)}` : '—' },
  { key: 'valueEur', label: 'Value €', fmt: t => eur(t.valueEur) },
];

function shortPosition(p) {
  if (!p) return '';
  if (/CEO|Chief Executive|Managing Director/i.test(p)) return 'CEO';
  if (/CFO|Chief Financial/i.test(p)) return 'CFO';
  if (/Chair/i.test(p)) return 'Chair';
  if (/Board/i.test(p)) return 'Board member';
  return p.replace(/\s*\(.*?\)\s*/g, ' ').trim();
}

const FILTERS = [
  { id: 'side', label: 'Trade', options: [
      ['Buys of shares', t => side(t) === 'buy'], ['Sells of shares', t => side(t) === 'sell'],
      ['Buys and sells', t => side(t) !== 'other'], ['Options, gifts and other', t => side(t) === 'other']], def: 2 },
  { id: 'value', label: 'Value', options: [
      ['Over €1M', t => t.valueEur > 1e6], ['Over €100k', t => t.valueEur > 1e5], ['Over €10k', t => t.valueEur > 1e4]] },
  { id: 'who', label: 'Who', options: [
      ['CEO', t => shortPosition(t.position) === 'CEO'], ['CEO or CFO', t => ['CEO', 'CFO'].includes(shortPosition(t.position))],
      ['Board', t => ['Chair', 'Board member'].includes(shortPosition(t.position))], ['Excluding related persons', t => t.associated !== 'Yes']] },
  { id: 'when', label: 'Published', options: [
      ['Today', t => daysAgo(t.published) < 1], ['Last 7 days', t => daysAgo(t.published) < 7], ['Last 30 days', t => daysAgo(t.published) < 30]] },
];

function renderFilters() {
  document.getElementById('co-filters').innerHTML = FILTERS.map(f =>
    `<div class="filter-item"><label for="f-${f.id}">${f.label}</label>
      <select id="f-${f.id}" data-filter="${f.id}"><option value="">Any</option>
      ${f.options.map(([label], i) => `<option value="${i}" ${f.def === i ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></div>`
  ).join('');
  FILTERS.forEach(f => { if (f.def !== undefined) filters[f.id] = f.def; });
  document.querySelectorAll('[data-filter]').forEach(sel => sel.addEventListener('change', () => {
    if (sel.value === '') delete filters[sel.dataset.filter]; else filters[sel.dataset.filter] = Number(sel.value);
    page = 1; render();
  }));
}

// Net share buying on trading venues per company over 30 days, with the number of distinct buyers.
function renderTop() {
  const by = {};
  TRADES.filter(t => t.signal && daysAgo(t.published) < 30).forEach(t => {
    const c = by[t.issuer] || (by[t.issuer] = { net: 0, buyers: new Set() });
    c.net += (side(t) === 'buy' ? 1 : -1) * (t.valueEur || 0);
    if (side(t) === 'buy') c.buyers.add(t.person);
  });
  const top = Object.entries(by).filter(([, c]) => c.net > 0).sort((a, b) => b[1].net - a[1].net).slice(0, 10);
  document.getElementById('ins-top').innerHTML = top.map(([name, c]) =>
    `<li><a href="#" data-issuer="${esc(name)}">${esc(name)}</a><span>${eur(c.net)} · ${c.buyers.size} ${c.buyers.size === 1 ? 'buyer' : 'buyers'}</span></li>`
  ).join('') || '<li>No net buying yet.</li>';
}

function results() {
  const q = query.trim().toLowerCase();
  const active = FILTERS.filter(f => f.id in filters).map(f => f.options[filters[f.id]][1]);
  return TRADES.filter(t => active.every(test => test(t)) &&
      (!q || `${t.issuer} ${t.person} ${t.isin}`.toLowerCase().includes(q)))
    .sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (x == null || x === '') return 1;
      if (y == null || y === '') return -1;
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sortDir || (b.valueEur || 0) - (a.valueEur || 0);
    });
}

function render() {
  urlWriteFilters(FILTERS, filters, f => f.options, { q: query.trim() });
  const list = results();
  const pages = Math.max(1, Math.ceil(list.length / PAGE));
  page = Math.min(page, pages);
  const start = (page - 1) * PAGE;
  document.getElementById('co-count').textContent =
    `${list.length.toLocaleString('en-GB')} trades · ${META.source || ''} · updated ${META.updated || ''}`;
  const head = `<thead><tr><th class="col-no">#</th>${COLUMNS.map(c =>
    `<th class="sortable ${c.left ? 'l' : ''} ${sortKey === c.key ? 'sort-active' : ''}" data-sort="${c.key}">${c.label}${sortKey === c.key ? (sortDir < 0 ? ' ▼' : ' ▲') : ''}</th>`).join('')}</tr></thead>`;
  const body = '<tbody>' + list.slice(start, start + PAGE).map((t, i) =>
    `<tr class="stock-row ${t.status === 'Revoked' ? 'ins-revoked' : ''}"><td class="col-no">${start + i + 1}</td>
      ${COLUMNS.map(col => `<td class="${col.left ? 'l' : ''}">${col.fmt(t)}</td>`).join('')}</tr>`).join('') + '</tbody>';
  document.getElementById('screener-table').innerHTML = head + body;
  document.getElementById('pagination').innerHTML = `
    <button data-page="1" ${page <= 1 ? 'disabled' : ''}>«</button>
    <button data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>‹</button>
    <span>Page ${page} of ${pages}</span>
    <button data-page="${page + 1}" ${page >= pages ? 'disabled' : ''}>›</button>
    <button data-page="${pages}" ${page >= pages ? 'disabled' : ''}>»</button>`;
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    META = await (await fetch('js/insiders.json', { cache: 'no-cache' })).json();
    TRADES = META.rows || [];
  } catch (e) {
    document.getElementById('co-count').textContent = 'Could not load insider trades.';
    return;
  }
  renderFilters();
  renderTop();
  query = new URLSearchParams(location.search).get('q') || '';
  document.getElementById('co-search').value = query;
  urlReadFilters(FILTERS, filters, f => f.options);
  render();

  const search = document.getElementById('co-search');
  search.addEventListener('input', e => { query = e.target.value; page = 1; render(); });
  document.getElementById('ins-top').addEventListener('click', e => {
    const a = e.target.closest('[data-issuer]');
    if (!a) return;
    e.preventDefault();
    query = search.value = a.dataset.issuer; page = 1; render();
  });
  document.getElementById('co-reset').addEventListener('click', () => {
    Object.keys(filters).forEach(k => delete filters[k]);
    document.querySelectorAll('[data-filter]').forEach(s => s.value = '');
    query = search.value = ''; page = 1; render();
  });
  document.getElementById('screener-table').addEventListener('click', e => {
    const th = e.target.closest('[data-sort]');
    if (!th) return;
    const k = th.dataset.sort;
    if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = COLUMNS.find(c => c.key === k).left ? 1 : -1; }
    render();
  });
  document.getElementById('pagination').addEventListener('click', e => {
    const b = e.target.closest('[data-page]');
    if (b && !b.disabled) { page = Number(b.dataset.page); render(); window.scrollTo(0, 0); }
  });
});
