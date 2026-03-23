// Screener logic: filters, sorting, rendering

let sortKey = 'marketCap';
let sortDir = -1; // -1 desc, 1 asc
let currentFilters = {};
let currentPage = 1;
const PAGE_SIZE = 25;

const FILTER_DEFS = {
  exchange:    { label: 'Exchange',     type: 'select', options: ['Any', 'AEX','BIT','BME','EURONEXT','LSE','OMX','OSE','SIX','WBAG','WSE'] },
  country:     { label: 'Country',      type: 'select', options: ['Any', ...getCountries()] },
  sector:      { label: 'Sector',       type: 'select', options: ['Any', ...getSectors()] },
  industry:    { label: 'Industry',     type: 'select', options: ['Any', ...getIndustries()] },
  marketCapCat:{ label: 'Market Cap',   type: 'select', options: ['Any','Mega (>€200B)','Large (€10B-200B)','Mid (€2B-10B)','Small (€300M-2B)','Micro (<€300M)'] },
  peCat:       { label: 'P/E Ratio',    type: 'select', options: ['Any','Negative','Low (<15)','Normal (15-30)','High (30-50)','Very High (>50)'] },
  dividendCat: { label: 'Dividend Yield',type:'select', options: ['Any','None (0%)','Low (0-2%)','Moderate (2-4%)','High (>4%)'] },
  changeCat:   { label: '% Change',     type: 'select', options: ['Any','Down >5%','Down 2-5%','Down 0-2%','Up 0-2%','Up 2-5%','Up >5%'] },
  betaCat:     { label: 'Beta',         type: 'select', options: ['Any','Low (<0.5)','Normal (0.5-1)','Moderate (1-1.5)','High (>1.5)'] },
  rsiCat:      { label: 'RSI (14)',     type: 'select', options: ['Any','Oversold (<30)','Normal (30-70)','Overbought (>70)'] },
  perf52Cat:   { label: '52W Perf.',    type: 'select', options: ['Any','Down >30%','Down 10-30%','Down 0-10%','Up 0-10%','Up 10-30%','Up >30%'] },
};

function matchFilter(stock, filters) {
  for (const [key, val] of Object.entries(filters)) {
    if (!val || val === 'Any') continue;

    if (key === 'exchange' && stock.exchange !== val) return false;
    if (key === 'country'  && stock.country  !== val) return false;
    if (key === 'sector'   && stock.sector   !== val) return false;
    if (key === 'industry' && stock.industry !== val) return false;

    if (key === 'marketCapCat') {
      const mc = stock.marketCap;
      if (val.includes('>€200B')    && mc <= 200000) return false;
      if (val.includes('€10B-200B') && (mc < 10000 || mc >= 200000)) return false;
      if (val.includes('€2B-10B')   && (mc < 2000  || mc >= 10000))  return false;
      if (val.includes('€300M-2B')  && (mc < 300   || mc >= 2000))   return false;
      if (val.includes('<€300M')    && mc >= 300) return false;
    }

    if (key === 'peCat') {
      const pe = stock.pe;
      if (val === 'Negative'       && (pe === null || pe >= 0)) return false;
      if (val.includes('<15')      && (pe === null || pe < 0 || pe >= 15)) return false;
      if (val.includes('15-30')    && (pe === null || pe < 15 || pe >= 30)) return false;
      if (val.includes('30-50')    && (pe === null || pe < 30 || pe >= 50)) return false;
      if (val.includes('>50')      && (pe === null || pe < 50)) return false;
    }

    if (key === 'dividendCat') {
      const d = stock.dividend;
      if (val.includes('None')     && d > 0) return false;
      if (val.includes('0-2%')     && (d <= 0 || d >= 2)) return false;
      if (val.includes('2-4%')     && (d < 2  || d >= 4)) return false;
      if (val.includes('>4%')      && d < 4) return false;
    }

    if (key === 'changeCat') {
      const c = stock.change;
      if (val.includes('Down >5%') && c >= -5) return false;
      if (val.includes('Down 2-5%')&& (c < -5 || c >= -2)) return false;
      if (val.includes('Down 0-2%')&& (c < -2 || c >= 0))  return false;
      if (val.includes('Up 0-2%')  && (c < 0  || c >= 2))  return false;
      if (val.includes('Up 2-5%')  && (c < 2  || c >= 5))  return false;
      if (val.includes('Up >5%')   && c < 5) return false;
    }

    if (key === 'betaCat') {
      const b = stock.beta;
      if (val.includes('<0.5')    && b >= 0.5) return false;
      if (val.includes('0.5-1)')  && (b < 0.5 || b >= 1))  return false;
      if (val.includes('1-1.5')   && (b < 1   || b >= 1.5)) return false;
      if (val.includes('>1.5')    && b < 1.5) return false;
    }

    if (key === 'rsiCat') {
      const r = stock.rsi;
      if (val.includes('<30') && r >= 30) return false;
      if (val.includes('30-70') && (r < 30 || r >= 70)) return false;
      if (val.includes('>70')  && r < 70) return false;
    }

    if (key === 'perf52Cat') {
      const hi = stock.high52, lo = stock.low52, p = stock.price;
      const perf = ((p - lo) / (hi - lo) - 0.5) * 100; // rough
      const pct = ((p - lo) / lo) * 100;
      if (val.includes('Down >30%')   && pct >= -30) return false;
      if (val.includes('Down 10-30%') && (pct < -30 || pct >= -10)) return false;
      if (val.includes('Down 0-10%')  && (pct < -10 || pct >= 0))   return false;
      if (val.includes('Up 0-10%')    && (pct < 0   || pct >= 10))  return false;
      if (val.includes('Up 10-30%')   && (pct < 10  || pct >= 30))  return false;
      if (val.includes('Up >30%')     && pct < 30) return false;
    }
  }
  return true;
}

function applyFiltersAndSort() {
  let results = STOCKS.filter(s => matchFilter(s, currentFilters));
  results.sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (va === null || va === undefined) va = sortDir > 0 ? Infinity : -Infinity;
    if (vb === null || vb === undefined) vb = sortDir > 0 ? Infinity : -Infinity;
    return (va - vb) * sortDir;
  });
  return results;
}

function renderFilterPanel() {
  const panel = document.getElementById('filter-panel');
  if (!panel) return;
  panel.innerHTML = Object.entries(FILTER_DEFS).map(([key, def]) => {
    const opts = def.options.map(o =>
      `<option value="${o}"${currentFilters[key] === o ? ' selected' : ''}>${o}</option>`
    ).join('');
    return `<div class="filter-item">
      <label>${def.label}</label>
      <select data-filter="${key}" onchange="onFilterChange(this)">${opts}</select>
    </div>`;
  }).join('');
}

function onFilterChange(sel) {
  currentFilters[sel.dataset.filter] = sel.value;
  currentPage = 1;
  renderTable();
  renderStats();
}

function renderStats() {
  const results = applyFiltersAndSort();
  const el = document.getElementById('result-count');
  if (el) el.textContent = `${results.length} stocks matched`;
}

const COLUMNS = [
  { key: 'ticker',        label: 'Ticker',     fmt: s => `<a class="ticker-link" onclick="openStock('${s.ticker}')">${s.ticker}</a>` },
  { key: 'name',          label: 'Company',    fmt: s => `<span class="company-name" title="${s.name}">${s.name}</span>` },
  { key: 'sector',        label: 'Sector',     fmt: s => `<span class="badge badge-sector">${s.sector}</span>` },
  { key: 'country',       label: 'Country',    fmt: s => `<span class="flag">${countryFlag(s.country)}</span> ${s.country}` },
  { key: 'exchange',      label: 'Exchange',   fmt: s => s.exchange },
  { key: 'marketCap',     label: 'Mkt Cap',    fmt: s => formatMarketCap(s.marketCap) },
  { key: 'pe',            label: 'P/E',        fmt: s => s.pe ? formatNumber(s.pe,1) : '-' },
  { key: 'forwardPE',     label: 'Fwd P/E',   fmt: s => s.forwardPE ? formatNumber(s.forwardPE,1) : '-' },
  { key: 'eps',           label: 'EPS',        fmt: s => formatNumber(s.eps,2) },
  { key: 'dividend',      label: 'Div %',      fmt: s => formatNumber(s.dividend,2) + '%' },
  { key: 'price',         label: 'Price',      fmt: s => '€' + formatNumber(s.price,2) },
  { key: 'change',        label: 'Chg %',      fmt: s => `<span class="${changeColor(s.change)}">${formatPct(s.change)}</span>` },
  { key: 'volume',        label: 'Volume',     fmt: s => formatVol(s.volume) },
  { key: 'high52',        label: '52W Hi',     fmt: s => formatNumber(s.high52,2) },
  { key: 'low52',         label: '52W Lo',     fmt: s => formatNumber(s.low52,2) },
  { key: 'beta',          label: 'Beta',       fmt: s => formatNumber(s.beta,2) },
  { key: 'rsi',           label: 'RSI',        fmt: s => `<span class="rsi-badge ${rsiClass(s.rsi)}">${formatNumber(s.rsi,1)}</span>` },
  { key: 'revenueGrowth', label: 'Rev Gr',     fmt: s => `<span class="${changeColor(s.revenueGrowth)}">${formatPct(s.revenueGrowth)}</span>` },
  { key: 'epsGrowth',     label: 'EPS Gr',     fmt: s => s.epsGrowth ? `<span class="${changeColor(s.epsGrowth)}">${formatPct(s.epsGrowth)}</span>` : '-' },
  { key: 'grossMargin',   label: 'Gross M',    fmt: s => formatNumber(s.grossMargin,1) + '%' },
  { key: 'operatingMargin',label:'Oper M',     fmt: s => `<span class="${changeColor(s.operatingMargin)}">${formatNumber(s.operatingMargin,1)}%</span>` },
  { key: 'netMargin',     label: 'Net M',      fmt: s => `<span class="${changeColor(s.netMargin)}">${formatNumber(s.netMargin,1)}%</span>` },
  { key: 'roe',           label: 'ROE',        fmt: s => `<span class="${changeColor(s.roe)}">${formatNumber(s.roe,1)}%</span>` },
];

function formatVol(v) {
  if (v >= 1000000) return (v/1000000).toFixed(1) + 'M';
  if (v >= 1000)    return (v/1000).toFixed(0) + 'K';
  return v;
}

function rsiClass(r) {
  if (r < 30) return 'rsi-low';
  if (r > 70) return 'rsi-high';
  return 'rsi-mid';
}

function countryFlag(c) {
  const flags = {
    'Germany':'🇩🇪','France':'🇫🇷','UK':'🇬🇧','Netherlands':'🇳🇱',
    'Switzerland':'🇨🇭','Spain':'🇪🇸','Italy':'🇮🇹','Sweden':'🇸🇪',
    'Denmark':'🇩🇰','Finland':'🇫🇮','Belgium':'🇧🇪','Norway':'🇳🇴',
    'Ireland':'🇮🇪','Austria':'🇦🇹','Portugal':'🇵🇹','Poland':'🇵🇱',
  };
  return flags[c] || '🏳️';
}

function renderTable() {
  const results = applyFiltersAndSort();
  const start = (currentPage - 1) * PAGE_SIZE;
  const page = results.slice(start, start + PAGE_SIZE);
  const total = results.length;
  const pages = Math.ceil(total / PAGE_SIZE);

  const el = document.getElementById('screener-table');
  if (!el) return;

  const thead = `<thead><tr><th class="col-no">#</th>${COLUMNS.map(c =>
    `<th class="sortable ${sortKey === c.key ? 'sort-active' : ''}" onclick="onSort('${c.key}')">
      ${c.label}${sortKey === c.key ? (sortDir < 0 ? ' ▼' : ' ▲') : ''}
    </th>`
  ).join('')}</tr></thead>`;

  const tbody = '<tbody>' + page.map((s, i) =>
    `<tr class="stock-row" data-ticker="${s.ticker}">
      <td class="col-no">${start + i + 1}</td>
      ${COLUMNS.map(c => `<td>${c.fmt(s)}</td>`).join('')}
    </tr>`
  ).join('') + '</tbody>';

  el.innerHTML = thead + tbody;

  // pagination
  const pag = document.getElementById('pagination');
  if (pag) {
    pag.innerHTML = `
      <button onclick="gotoPage(1)" ${currentPage<=1?'disabled':''}>«</button>
      <button onclick="gotoPage(${currentPage-1})" ${currentPage<=1?'disabled':''}>‹</button>
      <span>Page ${currentPage} of ${pages} &nbsp;(${total} results)</span>
      <button onclick="gotoPage(${currentPage+1})" ${currentPage>=pages?'disabled':''}>›</button>
      <button onclick="gotoPage(${pages})" ${currentPage>=pages?'disabled':''}>»</button>
    `;
  }
}

function onSort(key) {
  if (sortKey === key) sortDir *= -1;
  else { sortKey = key; sortDir = -1; }
  renderTable();
}

function gotoPage(p) {
  const results = applyFiltersAndSort();
  const pages = Math.ceil(results.length / PAGE_SIZE);
  currentPage = Math.max(1, Math.min(p, pages));
  renderTable();
}

function openStock(ticker) {
  const s = STOCKS.find(x => x.ticker === ticker);
  if (!s) return;
  const modal = document.getElementById('stock-modal');
  const content = document.getElementById('modal-content');
  if (!modal || !content) return;

  const perf52 = (((s.price - s.low52) / (s.high52 - s.low52)) * 100).toFixed(0);
  content.innerHTML = `
    <div class="modal-header">
      <div>
        <h2>${s.ticker} <span class="modal-name">${s.name}</span></h2>
        <div class="modal-meta">${countryFlag(s.country)} ${s.country} &bull; ${s.exchange} &bull; ${s.sector} &bull; ${s.industry}</div>
      </div>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-price-row">
      <span class="modal-price">€${formatNumber(s.price,2)}</span>
      <span class="modal-change ${changeColor(s.change)}">${formatPct(s.change)}</span>
      <span class="modal-vol">Vol: ${formatVol(s.volume)}</span>
    </div>
    <div class="modal-sparkline">${sparklineHTML(s.ticker)}</div>
    <div class="modal-grid">
      <div class="modal-section">
        <h4>Valuation</h4>
        <table class="kv-table">
          <tr><td>Market Cap</td><td>${formatMarketCap(s.marketCap)}</td></tr>
          <tr><td>P/E Ratio</td><td>${s.pe ? formatNumber(s.pe,2) : 'N/A'}</td></tr>
          <tr><td>Forward P/E</td><td>${formatNumber(s.forwardPE,2)}</td></tr>
          <tr><td>Price/Book</td><td>${formatNumber(s.pb,2)}</td></tr>
          <tr><td>Price/Sales</td><td>${formatNumber(s.ps,2)}</td></tr>
          <tr><td>EPS</td><td>€${formatNumber(s.eps,2)}</td></tr>
          <tr><td>Dividend Yield</td><td>${formatNumber(s.dividend,2)}%</td></tr>
        </table>
      </div>
      <div class="modal-section">
        <h4>Performance</h4>
        <table class="kv-table">
          <tr><td>52W High</td><td>${formatNumber(s.high52,2)}</td></tr>
          <tr><td>52W Low</td><td>${formatNumber(s.low52,2)}</td></tr>
          <tr><td>52W Range</td><td>${perf52}%</td></tr>
          <tr><td>Beta</td><td>${formatNumber(s.beta,2)}</td></tr>
          <tr><td>RSI (14)</td><td><span class="rsi-badge ${rsiClass(s.rsi)}">${formatNumber(s.rsi,1)}</span></td></tr>
          <tr><td>Avg Volume</td><td>${formatVol(s.avgVolume)}</td></tr>
        </table>
      </div>
      <div class="modal-section">
        <h4>Profitability</h4>
        <table class="kv-table">
          <tr><td>Gross Margin</td><td>${formatNumber(s.grossMargin,1)}%</td></tr>
          <tr><td>Oper. Margin</td><td><span class="${changeColor(s.operatingMargin)}">${formatNumber(s.operatingMargin,1)}%</span></td></tr>
          <tr><td>Net Margin</td><td><span class="${changeColor(s.netMargin)}">${formatNumber(s.netMargin,1)}%</span></td></tr>
          <tr><td>ROE</td><td><span class="${changeColor(s.roe)}">${formatNumber(s.roe,1)}%</span></td></tr>
          <tr><td>D/E Ratio</td><td>${formatNumber(s.de,2)}</td></tr>
        </table>
      </div>
      <div class="modal-section">
        <h4>Growth</h4>
        <table class="kv-table">
          <tr><td>Revenue Growth</td><td><span class="${changeColor(s.revenueGrowth)}">${formatPct(s.revenueGrowth)}</span></td></tr>
          <tr><td>EPS Growth</td><td>${s.epsGrowth ? `<span class="${changeColor(s.epsGrowth)}">${formatPct(s.epsGrowth)}</span>` : 'N/A'}</td></tr>
        </table>
      </div>
    </div>
  `;
  modal.style.display = 'flex';
}

function closeModal() {
  document.getElementById('stock-modal').style.display = 'none';
}

function resetFilters() {
  currentFilters = {};
  currentPage = 1;
  document.querySelectorAll('#filter-panel select').forEach(s => s.value = 'Any');
  renderTable();
  renderStats();
}

document.addEventListener('DOMContentLoaded', () => {
  renderFilterPanel();
  renderTable();
  renderStats();
  document.getElementById('stock-modal')?.addEventListener('click', e => {
    if (e.target.id === 'stock-modal') closeModal();
  });
});
