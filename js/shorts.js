// FINILA short positions: funds' net short positions (0.5 % and more) from js/shorts.json,
// built twice a day by scripts/data/shorts.py from the regulators' registers.

const PAGE = 50;
let POSITIONS = [], COMPANIES = [], META = {};
let page = 1, query = '', view = 'companies', sortKey = 'total', sortDir = -1;
const filters = {};

const isNum = v => typeof v === 'number' && isFinite(v);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = v => isNum(v) ? `${v.toFixed(2)} %` : '—';
const change = v => !isNum(v) ? '—' : Math.abs(v) < 0.005 ? '0.00'
  : `<span class="${v > 0 ? 'neg' : 'pos'}">${v > 0 ? '+' : ''}${v.toFixed(2)}</span>`;
const daysAgo = d => (Date.now() - new Date(d).getTime()) / 864e5;
// The UK publishes one aggregated position per company, without fund names.
const AGG = p => p.c === 'UK';
const COUNTRY = { NL: 'Netherlands', IT: 'Italy', SE: 'Sweden', NO: 'Norway', UK: 'United Kingdom' };
// Registers write fund names in capitals or with legal suffixes; show them the same way everywhere.
const fund = h => /[a-z]/.test(h) ? h : h.toLowerCase().replace(/\b[a-z]/g, c => c.toUpperCase())
  .replace(/\b(Llc|Lp|Ltd|Plc|Ag|Sa|Ab|As|Nv|Bv|Se|Gmbh|Llp|Icav|Ii|Iii)\b/g, s => s.toUpperCase());

const COLUMNS = {
  companies: [
    { key: 'issuer', label: 'Company', left: true, fmt: c => `<a href="#" class="company-name" data-issuer="${esc(c.isin)}">${esc(c.issuer)}</a>` },
    { key: 'c', label: 'Country', left: true, fmt: c => esc(COUNTRY[c.c] || c.c) },
    { key: 'total', label: 'Shorted', fmt: c => `<b>${pct(c.total)}</b>` },
    { key: 'change', label: `Change ${'30d'}`, fmt: c => change(c.change) },
    { key: 'funds', label: 'Funds', fmt: c => AGG(c) ? '<span class="ins-note">n/a</span>' : c.funds },
    { key: 'top', label: 'Largest short', left: true, fmt: c => AGG(c) ? '<span class="ins-note">UK publishes no fund names</span>'
      : `<span class="company-name">${esc(fund(c.top.holder))} <span class="ins-note">${pct(c.top.pct)}</span></span>` },
    { key: 'latest', label: 'Last change', left: true, fmt: c => esc(c.latest) },
  ],
  positions: [
    { key: 'issuer', label: 'Company', left: true, fmt: p => `<span class="company-name">${esc(p.issuer)}</span>` },
    { key: 'holder', label: 'Fund', left: true, fmt: p => `<span class="company-name">${esc(fund(p.holder))}</span>` },
    { key: 'c', label: 'Country', left: true, fmt: p => esc(COUNTRY[p.c] || p.c) },
    { key: 'pct', label: 'Short', fmt: p => `<b>${pct(p.pct)}</b>` },
    { key: 'change', label: 'Change 30d', fmt: p => change(p.change) },
    { key: 'date', label: 'Position date', left: true, fmt: p => esc(p.date) },
  ],
};

const FILTERS = [
  { id: 'view', label: 'Show', options: [['By company', () => true], ['Every position', () => true]], def: 0, view: true },
  { id: 'country', label: 'Country', options: Object.entries(COUNTRY).map(([k, v]) => [v, r => r.c === k]) },
  { id: 'size', label: 'Shorted', options: [
      ['Over 5 %', r => (r.total ?? r.pct) > 5], ['Over 2 %', r => (r.total ?? r.pct) > 2], ['Over 1 %', r => (r.total ?? r.pct) > 1]] },
  { id: 'trend', label: 'Change, 30 days', options: [
      ['Rising', r => r.change > 0.004], ['Falling', r => r.change < -0.004], ['New in 30 days', r => r.isNew]] },
  { id: 'when', label: 'Last change', options: [
      ['Last 7 days', r => daysAgo(r.latest ?? r.date) < 7], ['Last 30 days', r => daysAgo(r.latest ?? r.date) < 30]] },
];

// One row per share: total short, number of funds, 30-day change where the register keeps history.
function buildCompanies() {
  const by = {};
  POSITIONS.forEach(p => {
    p.change = isNum(p.prev) ? p.pct - p.prev : null;
    p.isNew = p.prev === 0;
    const c = by[p.isin] || (by[p.isin] = { isin: p.isin, issuer: p.issuer, c: p.c, total: 0, prev: 0, funds: 0, top: p, latest: p.date, trend: true, list: [] });
    c.total += p.pct; c.funds += 1; c.list.push(p);
    if (isNum(p.prev)) c.prev += p.prev; else c.trend = false;
    if (p.pct > c.top.pct) c.top = p;
    if (p.date > c.latest) c.latest = p.date;
  });
  COMPANIES = Object.values(by).map(c => ({ ...c, total: +c.total.toFixed(2), change: c.trend ? c.total - c.prev : null, isNew: c.trend && c.prev === 0 }));
}

function renderFilters() {
  document.getElementById('co-filters').innerHTML = FILTERS.map(f =>
    `<div class="filter-item"><label for="f-${f.id}">${f.label}</label>
      <select id="f-${f.id}" data-filter="${f.id}">${f.view ? '' : '<option value="">Any</option>'}
      ${f.options.map(([label], i) => `<option value="${i}" ${f.def === i ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></div>`
  ).join('');
  document.querySelectorAll('[data-filter]').forEach(sel => sel.addEventListener('change', () => {
    if (sel.dataset.filter === 'view') { setView(sel.value === '1' ? 'positions' : 'companies'); return; }
    if (sel.value === '') delete filters[sel.dataset.filter]; else filters[sel.dataset.filter] = Number(sel.value);
    page = 1; render();
  }));
}

function setView(v) {
  view = v; page = 1;
  sortKey = v === 'companies' ? 'total' : 'pct'; sortDir = -1;
  document.getElementById('f-view').value = v === 'positions' ? '1' : '0';
  render();
}

// Funds with the most open positions, and their total across companies.
function renderTop() {
  const by = {};
  POSITIONS.filter(p => !AGG(p)).forEach(p => {
    const f = by[p.holder.toLowerCase()] || (by[p.holder.toLowerCase()] = { name: fund(p.holder), n: 0 });
    f.n += 1;
  });
  const top = Object.values(by).sort((a, b) => b.n - a.n).slice(0, 10);
  document.getElementById('ins-top').innerHTML = top.map(f =>
    `<li><a href="#" data-fund="${esc(f.name)}">${esc(f.name)}</a><span>${f.n} companies</span></li>`).join('');
}

function results() {
  const q = query.trim().toLowerCase();
  const active = FILTERS.filter(f => !f.view && f.id in filters).map(f => f.options[filters[f.id]][1]);
  const rows = view === 'companies' ? COMPANIES : POSITIONS;
  return rows.filter(r => active.every(test => test(r)) &&
      (!q || `${r.issuer} ${r.isin} ${view === 'companies' ? r.list.map(p => p.holder).join(' ') : r.holder}`.toLowerCase().includes(q)))
    .sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (x == null || x === '') return 1;
      if (y == null || y === '') return -1;
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sortDir;
    });
}

function render() {
  const list = results(), cols = COLUMNS[view];
  const pages = Math.max(1, Math.ceil(list.length / PAGE));
  page = Math.min(page, pages);
  const start = (page - 1) * PAGE;
  document.getElementById('co-count').textContent =
    `${list.length.toLocaleString('en-GB')} ${view === 'companies' ? 'companies' : 'positions'} · ${Object.keys(META.countries || {}).length} regulators · updated ${META.updated || ''}`;
  const head = `<thead><tr><th class="col-no">#</th>${cols.map(c =>
    `<th class="sortable ${c.left ? 'l' : ''} ${sortKey === c.key ? 'sort-active' : ''}" data-sort="${c.key}">${c.label}${sortKey === c.key ? (sortDir < 0 ? ' ▼' : ' ▲') : ''}</th>`).join('')}</tr></thead>`;
  const body = '<tbody>' + list.slice(start, start + PAGE).map((r, i) =>
    `<tr class="stock-row"><td class="col-no">${start + i + 1}</td>
      ${cols.map(col => `<td class="${col.left ? 'l' : ''}">${col.fmt(r)}</td>`).join('')}</tr>`).join('') + '</tbody>';
  document.getElementById('screener-table').innerHTML = head + body;
  document.getElementById('pagination').innerHTML = `
    <button data-page="1" ${page <= 1 ? 'disabled' : ''}>«</button>
    <button data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>‹</button>
    <span>Page ${page} of ${pages}</span>
    <button data-page="${page + 1}" ${page >= pages ? 'disabled' : ''}>›</button>
    <button data-page="${pages}" ${page >= pages ? 'disabled' : ''}>»</button>`;
}

function openCompany(isin) {
  const c = COMPANIES.find(x => x.isin === isin);
  if (!c) return;
  const src = (META.countries || {})[c.c] || {};
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-header">
      <div><h2>${esc(c.issuer)}</h2><div class="modal-meta">${esc(c.isin)} · ${esc(COUNTRY[c.c] || c.c)}</div></div>
      <button class="modal-close" type="button" aria-label="Close">×</button>
    </div>
    <p><b>${pct(c.total)}</b> of the shares are sold short${AGG(c) ? '' : ` by ${c.funds} ${c.funds === 1 ? 'fund' : 'funds'}`}${isNum(c.change) ? `, ${change(c.change)} points in 30 days` : ''}.</p>
    <table class="modal-table"><thead><tr><th class="l">Fund</th><th>Short</th><th>Change 30d</th><th class="l">Position date</th></tr></thead><tbody>
    ${c.list.sort((a, b) => b.pct - a.pct).map(p => `<tr><td class="l">${esc(fund(p.holder))}</td><td>${pct(p.pct)}</td><td>${change(p.change)}</td><td class="l">${esc(p.date)}</td></tr>`).join('')}
    </tbody></table>
    <p class="modal-report-src">Source: <a href="${esc(src.url)}" target="_blank" rel="noopener">${esc(src.name)}</a>. Positions under 0.5 % are not public, so the real total can be higher.</p>`;
  document.getElementById('stock-modal').style.display = 'flex';
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    META = await (await fetch('js/shorts.json', { cache: 'no-cache' })).json();
    POSITIONS = META.positions || [];
  } catch (e) {
    document.getElementById('co-count').textContent = 'Could not load short positions.';
    return;
  }
  buildCompanies();
  renderFilters();
  renderTop();
  query = new URLSearchParams(location.search).get('q') || '';
  const search = document.getElementById('co-search');
  search.value = query;
  render();

  search.addEventListener('input', e => { query = e.target.value; page = 1; render(); });
  document.getElementById('ins-top').addEventListener('click', e => {
    const a = e.target.closest('[data-fund]');
    if (!a) return;
    e.preventDefault();
    query = search.value = a.dataset.fund; setView('positions');
  });
  document.getElementById('co-reset').addEventListener('click', () => {
    Object.keys(filters).forEach(k => delete filters[k]);
    document.querySelectorAll('[data-filter]').forEach(s => { if (s.dataset.filter !== 'view') s.value = ''; });
    query = search.value = ''; setView('companies');
  });
  document.getElementById('screener-table').addEventListener('click', e => {
    const a = e.target.closest('[data-issuer]');
    if (a) { e.preventDefault(); openCompany(a.dataset.issuer); return; }
    const th = e.target.closest('[data-sort]');
    if (!th) return;
    const k = th.dataset.sort;
    if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = COLUMNS[view].find(c => c.key === k).left ? 1 : -1; }
    render();
  });
  document.getElementById('pagination').addEventListener('click', e => {
    const b = e.target.closest('[data-page]');
    if (b && !b.disabled) { page = Number(b.dataset.page); render(); window.scrollTo(0, 0); }
  });
  const modal = document.getElementById('stock-modal');
  modal.addEventListener('click', e => { if (e.target === modal || e.target.closest('.modal-close')) modal.style.display = 'none'; });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') modal.style.display = 'none'; });
});
