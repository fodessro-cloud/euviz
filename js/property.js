// FINILA — property prices by country (Eurostat house price index, OECD indicators).
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isNum = v => typeof v === 'number' && isFinite(v);
const pct = (v, d = 1) => isNum(v) ? `${v > 0 ? '+' : ''}${v.toFixed(d)} %` : '—';
const cls = v => isNum(v) ? (v > 0 ? 'pos' : v < 0 ? 'neg' : '') : '';
const COLORS = { nominal: '#1F6FEB', real: '#B97A0A' };

let DATA = null, code = 'SK', years = 10, sortKey = 'n10', sortDir = -1;

// "+23 %" against incomes reads as "expensive"; the words help readers who skip the numbers.
function valuationWord(v) {
  if (!isNum(v)) return '';
  if (v >= 15) return 'expensive';
  if (v >= 5) return 'somewhat expensive';
  if (v > -5) return 'about average';
  if (v > -15) return 'somewhat cheap';
  return 'cheap';
}

function quarterLabel(q) { return q ? q.replace('-', ' ') : ''; }

function tile(title, value, sub, klass = '') {
  return `<div class="i-tile"><div class="i-tile-head">${esc(title)}</div>
    <div class="i-tile-real ${klass}">${value}</div><div class="i-tile-sub">${sub}</div></div>`;
}

function renderNow() {
  const c = DATA.countries[code];
  const r = c.real || {};
  $('now').innerHTML = [
    tile('Last 12 months', pct(c.nominal['1y']), isNum(r['1y']) ? `${pct(r['1y'])} after inflation` : 'price change', cls(c.nominal['1y'])),
    tile('Last 10 years', pct(c.nominal['10y'], 0), isNum(r['10y']) ? `${pct(r['10y'], 0)} after inflation` : 'price change', cls(c.nominal['10y'])),
    tile('Price vs. incomes', isNum(c.vsIncome) ? pct(c.vsIncome, 0) : '—',
      isNum(c.vsIncome) ? `against the average since 2000: ${valuationWord(c.vsIncome)}` : 'not published for this country', cls(c.vsIncome)),
    tile('Price vs. rents', isNum(c.vsRent) ? pct(c.vsRent, 0) : '—',
      isNum(c.vsRent) ? `against the average since 2000: ${valuationWord(c.vsRent)}` : 'not published for this country', cls(c.vsRent)),
  ].join('');
  $('now-sub').innerHTML = `${esc(c.name)} · prices to <b>${esc(quarterLabel(c.latest))}</b>`;
}

function renderChart() {
  const c = DATA.countries[code];
  const keys = Object.keys(c.series.nominal).sort();
  const start = years ? keys[Math.max(0, keys.length - 1 - years * 4)] : keys[0];
  const lines = ['nominal', 'real'].filter(k => c.series[k]).map(k => {
    const s = c.series[k], ks = Object.keys(s).sort().filter(q => q >= start);
    const base = s[ks[0]];
    return { k, pts: ks.map(q => [q, (s[q] / base - 1) * 100]) };
  }).filter(l => l.pts.length > 1);
  const all = lines.flatMap(l => l.pts.map(p => p[1])).concat([0]);
  const lo = Math.min(...all), hi = Math.max(...all);
  const W = $('chart').clientWidth || 700, H = 300, L = 48, R = 12, T = 10, B = 26;
  const qs = [...new Set(lines.flatMap(l => l.pts.map(p => p[0])))].sort();
  const x = q => L + (W - L - R) * (qs.indexOf(q) / Math.max(1, qs.length - 1));
  const y = v => T + (H - T - B) * (1 - (v - lo) / ((hi - lo) || 1));
  const step = [10, 20, 25, 50, 100, 200].find(s => (hi - lo) / s <= 6) || 500;
  let grid = '';
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    grid += `<line class="${v === 0 ? 'base' : 'g'}" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v > 0 ? '+' : ''}${v}%</text>`;
  }
  const yearsShown = [...new Set(qs.map(q => q.slice(0, 4)))];
  const every = Math.ceil(yearsShown.length / 8);
  yearsShown.forEach((yr, i) => {
    const q = qs.find(k => k.startsWith(yr));
    if (i % every === 0) grid += `<text class="ax" x="${x(q)}" y="${H - 6}" text-anchor="middle">${yr}</text>`;
  });
  const paths = lines.map(l => `<path class="ln" stroke="${COLORS[l.k]}" d="${l.pts.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('')}"/>`).join('');
  $('chart').innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${grid}${paths}</svg>`;
  $('legend').innerHTML = lines.map(l => `<span><i style="background:${COLORS[l.k]}"></i>${l.k === 'nominal' ? 'Price change' : 'After inflation'}</span>`).join('');
  $('chart-title').textContent = `House prices in ${c.name}`;
  $('chart-sub').textContent = `Change since ${quarterLabel(start)}, all dwellings`;
}

const COLS = [
  { key: 'name', label: 'Country', get: c => c.name, fmt: c => esc(c.name) },
  { key: 'n1', label: '1 year', get: c => c.nominal['1y'] },
  { key: 'n5', label: '5 years', get: c => c.nominal['5y'] },
  { key: 'n10', label: '10 years', get: c => c.nominal['10y'] },
  { key: 'r10', label: '10 y after inflation', get: c => c.real && c.real['10y'] },
  { key: 'inc', label: 'vs. incomes', get: c => c.vsIncome, title: 'Price-to-income ratio against its average since 2000' },
  { key: 'rent', label: 'vs. rents', get: c => c.vsRent, title: 'Price-to-rent ratio against its average since 2000' },
  { key: 'val', label: 'Overall', get: c => c.valuation, title: 'Average of the two: above zero dearer than usual, below zero cheaper' },
];

function renderTable() {
  $('eu-head').innerHTML = `<tr>${COLS.map(col => `<th class="${col.key === 'name' ? '' : 'r'} sort" data-sort="${col.key}" ${col.title ? `title="${esc(col.title)}"` : ''}>${esc(col.label)}${sortKey === col.key ? (sortDir < 0 ? ' ▼' : ' ▲') : ''}</th>`).join('')}</tr>`;
  const col = COLS.find(c => c.key === sortKey);
  const rows = Object.entries(DATA.countries).sort(([, a], [, b]) => {
    const x = col.get(a), y = col.get(b);
    if (typeof x === 'string') return x.localeCompare(y) * sortDir;
    if (!isNum(x)) return 1;
    if (!isNum(y)) return -1;
    return (x - y) * sortDir;
  });
  $('eu-body').innerHTML = rows.map(([k, c]) => `<tr class="${k === code ? 'sel' : ''}" data-code="${k}">${COLS.map(col =>
    col.key === 'name' ? `<td>${esc(c.name)}</td>` : `<td class="r m ${cls(col.get(c))}">${pct(col.get(c), col.key === 'n1' ? 1 : 0)}</td>`).join('')}</tr>`).join('');
}

// Cheapest and dearest against incomes and rents: a fact about today's prices, not a forecast.
function renderValue() {
  const list = Object.entries(DATA.countries).filter(([, c]) => isNum(c.valuation)).sort((a, b) => a[1].valuation - b[1].valuation);
  const li = ([k, c]) => `<li><a href="?c=${k}" data-code="${k}">${esc(c.name)}</a><span class="m ${cls(c.valuation)}">${pct(c.valuation, 0)}</span></li>`;
  $('cheap').innerHTML = list.slice(0, 5).map(li).join('');
  $('dear').innerHTML = list.slice(-5).reverse().map(li).join('');
}

function renderAll() { renderNow(); renderChart(); renderTable(); }

async function init() {
  try {
    DATA = await (await fetch('js/housing.json', { cache: 'no-cache' })).json();
  } catch {
    $('now').innerHTML = '<p class="h-note">House price data could not be loaded. Please try again later.</p>';
    return;
  }
  const params = new URLSearchParams(location.search);
  if (DATA.countries[params.get('c')]) code = params.get('c');
  else if (!DATA.countries[code]) code = Object.keys(DATA.countries)[0];
  $('region').innerHTML = Object.entries(DATA.countries).sort((a, b) => a[1].name.localeCompare(b[1].name))
    .map(([k, c]) => `<option value="${k}" ${k === code ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  $('updated').textContent = `Updated ${DATA.updated.slice(0, 10)}`;
  $('sources').innerHTML = DATA.sources.map(([n, u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a></li>`).join('');
  $('region').addEventListener('change', e => { code = e.target.value; renderAll(); });
  $('years').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    years = Number(b.dataset.years);
    $('years').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    renderChart();
  });
  $('eu-head').addEventListener('click', e => {
    const th = e.target.closest('[data-sort]');
    if (!th) return;
    sortDir = sortKey === th.dataset.sort ? -sortDir : (th.dataset.sort === 'name' ? 1 : -1);
    sortKey = th.dataset.sort;
    renderTable();
  });
  $('eu-body').addEventListener('click', e => {
    const tr = e.target.closest('[data-code]');
    if (!tr) return;
    code = tr.dataset.code;
    $('region').value = code;
    renderAll();
    $('top').scrollIntoView({ behavior: 'smooth' });
  });
  document.querySelectorAll('.p-value ol').forEach(ol => ol.addEventListener('click', e => {
    const a = e.target.closest('[data-code]');
    if (!a) return;
    e.preventDefault();
    code = a.dataset.code;
    $('region').value = code;
    renderAll();
    $('top').scrollIntoView({ behavior: 'smooth' });
  }));
  window.addEventListener('resize', () => renderChart());
  renderValue();
  renderAll();
}

init();
