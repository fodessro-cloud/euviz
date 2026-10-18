// FINILA — property prices by country (Eurostat house price index, OECD indicators).
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isNum = v => typeof v === 'number' && isFinite(v);
const pct = (v, d = 1) => { if (!isNum(v)) return '—'; const s = v.toFixed(d); return `${v > 0 && Number(s) !== 0 ? '+' : ''}${Number(s) === 0 ? (0).toFixed(d) : s} %`; };
const cls = v => isNum(v) ? (v > 0 ? 'pos' : v < 0 ? 'neg' : '') : '';
const COLORS = { nominal: '#1F6FEB', real: '#B97A0A', eu: '#8A94A6' };
const EU = 'EU';

let DATA = null, LEVELS = null, MAP = null, code = EU, years = 10, sortKey = 'n10', sortDir = -1, metric = 'm2';
const eur = v => `€${Math.round(v).toLocaleString('en-GB')}`;

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
  ].join('') + (LEVELS?.countries[code] ? (() => {
    const l = LEVELS.countries[code];
    return tile('Price per m²', eur(l.eur), `${esc(l.what)}, ${esc(l.period)}`);
  })() : '');
  $('now-sub').innerHTML = `${esc(c.name)} · prices to <b>${esc(quarterLabel(c.latest))}</b>`;
}

function renderChart() {
  const c = DATA.countries[code];
  const keys = Object.keys(c.series.nominal).sort();
  const start = years ? keys[Math.max(0, keys.length - 1 - years * 4)] : keys[0];
  const src = ['nominal', 'real'].filter(k => c.series[k]).map(k => [k, c.series[k]]);
  // Europe as a whole next to the chosen country, so every country reads against the EU.
  if (code !== EU && DATA.countries[EU]) src.push(['eu', DATA.countries[EU].series.nominal]);
  const lines = src.map(([k, s]) => {
    const ks = Object.keys(s).sort().filter(q => q >= start && q <= c.latest);
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
  const paths = lines.map(l => `<path class="ln${l.k === 'eu' ? ' dash' : ''}" stroke="${COLORS[l.k]}" d="${l.pts.map((p, i) => `${i ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('')}"/>`).join('');
  $('chart').innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${grid}${paths}</svg>`;
  const LABEL = { nominal: 'Price change', real: 'After inflation', eu: 'European Union, price change' };
  $('legend').innerHTML = lines.map(l => `<span><i class="${l.k === 'eu' ? 'dash' : ''}" style="background:${COLORS[l.k]}"></i>${LABEL[l.k]}</span>`).join('');
  $('chart-title').textContent = code === EU ? 'House prices in the European Union' : `House prices in ${c.name}`;
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
  const agg = Object.entries(DATA.countries).filter(([, c]) => c.agg);
  const rows = Object.entries(DATA.countries).filter(([, c]) => !c.agg).sort(([, a], [, b]) => {
    const x = col.get(a), y = col.get(b);
    if (typeof x === 'string') return x.localeCompare(y) * sortDir;
    if (!isNum(x)) return 1;
    if (!isNum(y)) return -1;
    return (x - y) * sortDir;
  });
  $('eu-body').innerHTML = agg.concat(rows).map(([k, c]) => `<tr class="${k === code ? 'sel' : ''} ${c.agg ? 'agg' : ''}" data-code="${k}">${COLS.map(col =>
    col.key === 'name' ? `<td>${esc(c.name)}</td>` : `<td class="r m ${cls(col.get(c))}">${pct(col.get(c), col.key === 'n1' ? 1 : 0)}</td>`).join('')}</tr>`).join('');
}

// Cheapest and dearest against incomes and rents: a fact about today's prices, not a forecast.
function renderValue() {
  const list = Object.entries(DATA.countries).filter(([, c]) => !c.agg && isNum(c.valuation)).sort((a, b) => a[1].valuation - b[1].valuation);
  const li = ([k, c]) => `<li><a href="?c=${k}" data-code="${k}">${esc(c.name)}</a><span class="m ${cls(c.valuation)}">${pct(c.valuation, 0)}</span></li>`;
  $('cheap').innerHTML = list.slice(0, 5).map(li).join('');
  $('dear').innerHTML = list.slice(-5).reverse().map(li).join('');
}

// ── Map of Europe ─────────────────────────────────────
// Bins and colours per metric; prices and changes read light to dark, "cheap or expensive" blue to orange.
const BLUES = ['#DCE8F8', '#B4CDF0', '#86AEE6', '#5B8FD9', '#2F6FC4', '#1A4F96'];
const METRICS = {
  m2: { title: 'Price per m²', get: k => LEVELS?.countries[k]?.eur, fmt: eur, bins: [1500, 2000, 2500, 3000, 3500], colors: BLUES },
  n5: { title: 'Price change in 5 years', get: k => DATA.countries[k]?.nominal['5y'], fmt: v => pct(v, 0), bins: [0, 20, 40, 60, 80], colors: ['#F2C9C4', ...BLUES.slice(1)] },
  n10: { title: 'Price change in 10 years', get: k => DATA.countries[k]?.nominal['10y'], fmt: v => pct(v, 0), bins: [0, 30, 60, 100, 150], colors: ['#F2C9C4', ...BLUES.slice(1)] },
  val: { title: 'Cheap or expensive against incomes and rents', get: k => DATA.countries[k]?.valuation, fmt: v => pct(v, 0),
    bins: [-15, -5, 5, 15], colors: ['#2F6FC4', '#9DBDEB', '#E6E8EC', '#F2B98A', '#D9772B'], words: ['cheap', 'somewhat cheap', 'about average', 'somewhat expensive', 'expensive'] },
};
const colorOf = (m, v) => m.colors[m.bins.filter(b => v >= b).length];

function renderMap() {
  if (!MAP) { $('map-section').hidden = true; return; }
  const m = METRICS[metric];
  const paths = MAP.countries.map(c => {
    const v = c.id && !DATA.countries[c.id]?.agg ? m.get(c.id) : undefined;
    if (!c.id) return `<path class="ctx" d="${c.d}"/>`;
    if (!isNum(v)) return `<path class="nd ${c.id === code ? 'sel' : ''}" data-code="${c.id}" d="${c.d}"/>`;
    return `<path class="has ${c.id === code ? 'sel' : ''}" data-code="${c.id}" fill="${colorOf(m, v)}" d="${c.d}"/>`;
  });
  // Selected country drawn last so its outline sits on top.
  paths.sort((a, b) => a.includes(' sel') - b.includes(' sel'));
  $('map').innerHTML = `<svg viewBox="0 0 ${MAP.w} ${MAP.h}">${paths.join('')}</svg>`;
  const edges = [null, ...m.bins];
  $('map-scale').innerHTML = m.colors.map((col, i) => `<span><i style="background:${col}"></i>${m.words ? m.words[i]
    : i === 0 ? `under ${m.fmt(m.bins[0])}` : i === m.bins.length ? `${m.fmt(m.bins[i - 1])}+` : `${m.fmt(edges[i])} to ${m.fmt(m.bins[i])}`}</span>`).join('')
    + `<span><i style="background:var(--card2);border:1px solid var(--line2)"></i>no data</span>`;
}

function renderSide() {
  const m = METRICS[metric];
  $('side-title').textContent = m.title;
  const list = Object.keys(DATA.countries).concat(Object.keys(LEVELS?.countries || {}))
    .filter((k, i, a) => a.indexOf(k) === i && !DATA.countries[k]?.agg && isNum(m.get(k)))
    .sort((a, b) => m.get(b) - m.get(a));
  const name = k => DATA.countries[k]?.name || LEVELS.countries[k].name;
  // Asking prices and appraisals are not sale prices; say so next to the number.
  const BASIS = { asking: 'asking price', appraisal: 'bank appraisal' };
  const basis = k => metric === 'm2' && BASIS[LEVELS.countries[k].basis] ? ` <small>${BASIS[LEVELS.countries[k].basis]}</small>` : '';
  $('rank').innerHTML = list.map(k => `<li class="${k === code ? 'sel' : ''}"><a data-code="${k}">${esc(name(k))}</a>${basis(k)}<span class="m">${m.fmt(m.get(k))}</span></li>`).join('');
  const l = LEVELS?.countries[code];
  $('regions-box').hidden = !l?.regions?.length;
  if (l?.regions?.length) {
    $('regions-title').textContent = `Price per m² in ${l.name}: regions and cities`;
    $('regions').innerHTML = l.regions.map(r => `<li>${esc(r.name)}<span class="m">${eur(r.eur)}</span></li>`).join('');
  }
  $('map-note').innerHTML = metric === 'm2'
    ? `Official figures only, in euros. ${Object.values(LEVELS?.countries || {}).map(c => `${esc(c.name)}: ${esc(c.what)}, ${esc(c.period)}, ${esc(c.source)}`).join('. ')}. Asking prices and bank appraisals are usually higher than what buyers finally pay, so compare countries with care. More countries are being added.`
    : 'Eurostat house price index; OECD for the United Kingdom and for incomes and rents.';
}

function select(k) {
  code = k;
  if ([...$('region').options].some(o => o.value === k)) $('region').value = k;
  renderAll();
}

function renderAll() { renderNow(); renderChart(); renderTable(); renderMap(); renderSide(); }

async function init() {
  try {
    DATA = await (await fetch('js/housing.json', { cache: 'no-cache' })).json();
    [LEVELS, MAP] = await Promise.all(['js/housing-levels.json', 'js/europe-map.json']
      .map(f => fetch(f, { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).catch(() => null)));
  } catch {
    $('now').innerHTML = '<p class="h-note">House price data could not be loaded. Please try again later.</p>';
    return;
  }
  const params = new URLSearchParams(location.search);
  if (DATA.countries[params.get('c')]) code = params.get('c');
  else if (!DATA.countries[code]) code = Object.keys(DATA.countries)[0];
  $('region').innerHTML = Object.entries(DATA.countries).sort((a, b) => (b[1].agg ? 1 : 0) - (a[1].agg ? 1 : 0) || a[1].name.localeCompare(b[1].name))
    .map(([k, c]) => `<option value="${k}" ${k === code ? 'selected' : ''}>${esc(c.name)}</option>`).join('');
  $('updated').textContent = `Updated ${DATA.updated.slice(0, 10)}`;
  const levelSources = Object.values(LEVELS?.countries || {}).map(c => [`${c.source}: home prices in ${c.name}`, c.url]);
  $('sources').innerHTML = DATA.sources.concat(levelSources).map(([n, u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a></li>`).join('');
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
  $('metric').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    metric = b.dataset.metric;
    $('metric').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
    renderMap();
    renderSide();
  });
  const tip = document.createElement('div');
  tip.className = 'p-tip';
  tip.hidden = true;
  document.body.appendChild(tip);
  $('map').addEventListener('mousemove', e => {
    const k = e.target.closest('[data-code]')?.dataset.code;
    const m = METRICS[metric];
    if (!k) { tip.hidden = true; return; }
    const v = m.get(k);
    tip.innerHTML = `<b>${esc(DATA.countries[k]?.name || LEVELS?.countries[k]?.name || k)}</b> ${isNum(v) ? m.fmt(v) : 'no data yet'}`;
    tip.style.left = `${e.clientX + 12}px`;
    tip.style.top = `${e.clientY + 12}px`;
    tip.hidden = false;
  });
  $('map').addEventListener('mouseleave', () => { tip.hidden = true; });
  ['map', 'rank'].forEach(id => $(id).addEventListener('click', e => {
    const k = e.target.closest('[data-code]')?.dataset.code;
    if (k && DATA.countries[k]) select(k);
  }));
  window.addEventListener('resize', () => renderChart());
  renderValue();
  renderAll();
}

init();
