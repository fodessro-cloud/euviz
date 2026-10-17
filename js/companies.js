// FINILA fundamentals screener: real figures from annual reports (js/companies.json,
// built by scripts/data/universe.py). Amounts are in millions of the report currency.

const PAGE = 50;
let COMPANIES = [], UPDATED = '';
let sortKey = 'revenueEur', sortDir = -1, page = 1, query = '';
const filters = {};

const isNum = v => typeof v === 'number' && isFinite(v);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const num = (v, d = 1) => isNum(v) ? v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—';
const pctCell = v => isNum(v) ? `<span class="${v >= 0 ? 'pos' : 'neg'}">${num(v)}%</span>` : '—';
const bn = (v, cur = '') => isNum(v) ? `${num(v / 1000, 2)}B${cur ? ' ' + cur : ''}` : '—';
const countryNames = (() => {
  try { return new Intl.DisplayNames(['en'], { type: 'region' }); } catch { return null; }
})();
const countryName = c => (c && countryNames ? countryNames.of(c) : c) || '—';
const ndCell = v => isNum(v) ? (v < 0 ? '<span class="pos">net cash</span>' : `${num(v, 2)}×`) : '—';

const COLUMNS = [
  { key: 'name', label: 'Company', left: true, fmt: c => `<span class="ticker-link">${esc(c.ticker || '')}</span> <span class="company-name">${esc(c.name)}</span>` },
  { key: 'country', label: 'Country', left: true, fmt: c => esc(countryName(c.country)) },
  { key: 'sector', label: 'Sector', left: true, fmt: c => c.sector ? `<span class="badge-sector">${esc(c.sector)}</span>` : '—' },
  { key: 'periodEnd', label: 'FY end', fmt: c => esc(c.periodEnd) },
  { key: 'revenueEur', label: 'Revenue €', fmt: c => bn(c.revenueEur) },
  { key: 'revenueGrowth', label: 'Rev. growth', fmt: c => pctCell(c.revenueGrowth) },
  { key: 'netMargin', label: 'Net margin', fmt: c => pctCell(c.netMargin) },
  { key: 'ebitdaMargin', label: 'EBITDA margin', fmt: c => pctCell(c.ebitdaMargin) },
  { key: 'fcfMargin', label: 'FCF margin', fmt: c => pctCell(c.fcfMargin) },
  { key: 'roe', label: 'ROE', fmt: c => pctCell(c.roe) },
  { key: 'netDebtToEbitda', label: 'Net debt/EBITDA', fmt: c => ndCell(c.netDebtToEbitda) },
  { key: 'netIncomeGrowth', label: 'Profit growth', fmt: c => pctCell(c.netIncomeGrowth) },
];

// Each filter: options as [label, test]
const FILTERS = [
  { id: 'country', label: 'Country', options: () => [...new Set(COMPANIES.map(c => c.country).filter(Boolean))]
      .sort((a, b) => countryName(a).localeCompare(countryName(b))).map(k => [countryName(k), c => c.country === k]) },
  { id: 'sector', label: 'Sector', options: () => [...new Set(COMPANIES.map(c => c.sector).filter(Boolean))].sort()
      .map(k => [k, c => c.sector === k]).concat([['Unknown', c => !c.sector]]) },
  { id: 'size', label: 'Revenue', options: () => [
      ['Over €50B', c => c.revenueEur > 50000], ['Over €10B', c => c.revenueEur > 10000],
      ['Over €1B', c => c.revenueEur > 1000], ['€100M to €1B', c => c.revenueEur >= 100 && c.revenueEur <= 1000],
      ['Under €100M', c => isNum(c.revenueEur) && c.revenueEur < 100]] },
  { id: 'roe', label: 'ROE', options: () => [
      ['Over 25%', c => c.roe > 25], ['Over 15%', c => c.roe > 15], ['Over 10%', c => c.roe > 10],
      ['Positive', c => c.roe > 0], ['Negative', c => c.roe < 0]] },
  { id: 'netMargin', label: 'Net margin', options: () => [
      ['Over 20%', c => c.netMargin > 20], ['Over 10%', c => c.netMargin > 10], ['Over 5%', c => c.netMargin > 5],
      ['Positive', c => c.netMargin > 0], ['Loss-making', c => c.netMargin < 0]] },
  { id: 'growth', label: 'Revenue growth', options: () => [
      ['Over 20%', c => c.revenueGrowth > 20], ['Over 10%', c => c.revenueGrowth > 10],
      ['Positive', c => c.revenueGrowth > 0], ['Shrinking', c => c.revenueGrowth < 0]] },
  { id: 'fcf', label: 'Free cash flow', options: () => [
      ['Positive', c => c.fcf > 0], ['FCF margin over 10%', c => c.fcfMargin > 10], ['Negative', c => c.fcf < 0]] },
  { id: 'debt', label: 'Net debt/EBITDA', options: () => [
      ['Net cash', c => c.netDebtToEbitda < 0], ['Under 1×', c => isNum(c.netDebtToEbitda) && c.netDebtToEbitda < 1],
      ['Under 2×', c => isNum(c.netDebtToEbitda) && c.netDebtToEbitda < 2], ['Over 3×', c => c.netDebtToEbitda > 3]] },
  { id: 'dividend', label: 'Dividends', options: () => [['Pays dividends', c => c.dividendsPaid > 0], ['No dividend', c => !(c.dividendsPaid > 0)]] },
  { id: 'type', label: 'Company type', options: () => [['Banks & insurers', c => c.financial], ['Excluding banks & insurers', c => !c.financial]] },
];

function renderFilters() {
  document.getElementById('co-filters').innerHTML = FILTERS.map(f => {
    f.opts = f.options();
    return `<div class="filter-item"><label for="f-${f.id}">${f.label}</label>
      <select id="f-${f.id}" data-filter="${f.id}"><option value="">Any</option>
      ${f.opts.map(([label], i) => `<option value="${i}">${esc(label)}</option>`).join('')}</select></div>`;
  }).join('');
  document.querySelectorAll('[data-filter]').forEach(sel => sel.addEventListener('change', () => {
    if (sel.value === '') delete filters[sel.dataset.filter]; else filters[sel.dataset.filter] = Number(sel.value);
    page = 1; render();
  }));
}

function results() {
  const q = query.trim().toLowerCase();
  const active = FILTERS.filter(f => f.id in filters).map(f => f.opts[filters[f.id]][1]);
  const list = COMPANIES.filter(c => active.every(t => t(c)) &&
    (!q || `${c.name} ${c.ticker || ''} ${countryName(c.country)} ${c.industry || ''}`.toLowerCase().includes(q)));
  return list.sort((a, b) => {
    const x = a[sortKey], y = b[sortKey];
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sortDir;
  });
}

function render() {
  const list = results();
  const pages = Math.max(1, Math.ceil(list.length / PAGE));
  page = Math.min(page, pages);
  const start = (page - 1) * PAGE;
  document.getElementById('co-count').textContent =
    `${list.length.toLocaleString('en-GB')} companies · annual reports read ${UPDATED}`;
  const head = `<thead><tr><th class="col-no">#</th>${COLUMNS.map(c =>
    `<th class="sortable ${c.left ? 'l' : ''} ${sortKey === c.key ? 'sort-active' : ''}" data-sort="${c.key}">${c.label}${sortKey === c.key ? (sortDir < 0 ? ' ▼' : ' ▲') : ''}</th>`).join('')}</tr></thead>`;
  const body = '<tbody>' + list.slice(start, start + PAGE).map((c, i) =>
    `<tr class="stock-row" data-lei="${esc(c.lei)}"><td class="col-no">${start + i + 1}</td>
      ${COLUMNS.map(col => `<td class="${col.left ? 'l' : ''}">${col.fmt(c)}</td>`).join('')}</tr>`).join('') + '</tbody>';
  document.getElementById('screener-table').innerHTML = head + body;
  document.getElementById('pagination').innerHTML = `
    <button data-page="1" ${page <= 1 ? 'disabled' : ''}>«</button>
    <button data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>‹</button>
    <span>Page ${page} of ${pages}</span>
    <button data-page="${page + 1}" ${page >= pages ? 'disabled' : ''}>›</button>
    <button data-page="${pages}" ${page >= pages ? 'disabled' : ''}>»</button>`;
}

function openCompany(lei) {
  const c = COMPANIES.find(x => x.lei === lei);
  if (!c) return;
  const cur = c.currency || '';
  const row = (k, v) => `<tr><td>${k}</td><td>${v}</td></tr>`;
  const fin = c.financial ? '<p class="modal-report-src">Bank or insurer: EBITDA, free cash flow and net debt are not shown because they do not describe these businesses well.</p>' : '';
  document.getElementById('modal-content').innerHTML = `
    <div class="modal-header">
      <div>
        <h2>${esc(c.name)} ${c.ticker ? `<span class="modal-name">${esc(c.ticker)}${c.exchange ? ' · ' + esc(c.exchange) : ''}</span>` : ''}</h2>
        <div class="modal-meta">${esc(countryName(c.country))}${c.sector ? ' · ' + esc(c.sector) : ''}${c.industry ? ' · ' + esc(c.industry) : ''}</div>
      </div>
      <button class="modal-close" type="button" data-close>✕</button>
    </div>
    <div class="modal-report">
      <div class="modal-report-head">
        <h4>Latest annual report · FY ending ${esc(c.periodEnd)} · ${esc(cur)}</h4>
        <span class="real-badge">Real data</span>
      </div>
      <div class="modal-grid">
        <div class="modal-section"><h4>Income</h4><table class="kv-table">
          ${row('Revenue', bn(c.revenue, cur))}${row('EBITDA', bn(c.ebitda, cur))}${row('Operating profit', bn(c.operatingProfit, cur))}${row('Net income', bn(c.netIncome, cur))}${row('EPS', isNum(c.eps) ? num(c.eps, 2) + ' ' + esc(cur) : '—')}
        </table></div>
        <div class="modal-section"><h4>Cash flow</h4><table class="kv-table">
          ${row('Operating cash flow', bn(c.operatingCashFlow, cur))}${row('Capex', bn(c.capex, cur))}${row('Free cash flow', bn(c.fcf, cur))}${row('Dividends paid', bn(c.dividendsPaid, cur))}
        </table></div>
        <div class="modal-section"><h4>Balance sheet</h4><table class="kv-table">
          ${row('Total assets', bn(c.assets, cur))}${row('Equity', bn(c.equity, cur))}${row('Cash', bn(c.cash, cur))}${row('Borrowings', bn(c.debt, cur))}${row('Net debt', bn(c.netDebt, cur))}
        </table></div>
        <div class="modal-section"><h4>Ratios</h4><table class="kv-table">
          ${row('ROE', pctCell(c.roe))}${row('EBITDA margin', pctCell(c.ebitdaMargin))}${row('Operating margin', pctCell(c.operatingMargin))}${row('Net margin', pctCell(c.netMargin))}${row('FCF margin', pctCell(c.fcfMargin))}${row('Net debt / EBITDA', ndCell(c.netDebtToEbitda))}${row('Revenue growth', pctCell(c.revenueGrowth))}${row('Net income growth', pctCell(c.netIncomeGrowth))}
        </table></div>
      </div>
      ${fin}
      <div class="modal-report-src">Source: the company’s ESEF annual report via filings.xbrl.org${c.source ? ` · <a href="${esc(c.source)}" target="_blank" rel="noopener">view report</a>` : ''}. Figures are read automatically and can contain errors; check the report before relying on them.</div>
    </div>`;
  document.getElementById('stock-modal').style.display = 'flex';
}

function closeCompany() { document.getElementById('stock-modal').style.display = 'none'; }

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const data = await (await fetch('js/companies.json')).json();
    UPDATED = data.updated;
    COMPANIES = data.rows.map(r => Object.fromEntries(data.fields.map((f, i) => [f, r[i]])));
  } catch (e) {
    document.getElementById('co-count').textContent = 'Could not load company data.';
    return;
  }
  renderFilters();
  const params = new URLSearchParams(location.search);
  query = params.get('q') || '';
  document.getElementById('co-search').value = query;
  render();
  if (params.get('lei')) openCompany(params.get('lei'));

  document.getElementById('co-search').addEventListener('input', e => { query = e.target.value; page = 1; render(); });
  document.getElementById('co-reset').addEventListener('click', () => {
    Object.keys(filters).forEach(k => delete filters[k]);
    document.querySelectorAll('[data-filter]').forEach(s => s.value = '');
    query = ''; document.getElementById('co-search').value = ''; page = 1; render();
  });
  document.getElementById('screener-table').addEventListener('click', e => {
    const th = e.target.closest('[data-sort]');
    if (th) {
      const k = th.dataset.sort;
      if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = COLUMNS.find(c => c.key === k).left ? 1 : -1; }
      render(); return;
    }
    const tr = e.target.closest('[data-lei]');
    if (tr) openCompany(tr.dataset.lei);
  });
  document.getElementById('pagination').addEventListener('click', e => {
    const b = e.target.closest('[data-page]');
    if (b && !b.disabled) { page = Number(b.dataset.page); render(); window.scrollTo(0, 0); }
  });
  document.getElementById('stock-modal').addEventListener('click', e => {
    if (e.target.id === 'stock-modal' || e.target.closest('[data-close]')) closeCompany();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeCompany(); });
});
