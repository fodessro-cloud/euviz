// FINILA "Where to put money": real returns of deposits, bonds, stocks, gold and property in every
// European country, against inflation. Data: js/invest.json, built daily by scripts/data/invest.py
// from the ECB, Eurostat and the World Bank.

// Categorical colours in a fixed order, validated for colour-blind separation: the dark steps on a
// dark page, the light steps on a light one (picked from the page background, so a theme change
// in the shared CSS carries over).
const PALETTE = {
  dark:  ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#3fa63f'],
  light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300'],
};
const ASSETS = [
  { key: 'stocks',  label: 'Stocks' },  // EURO STOXX 50 incl. estimated dividends
  { key: 'bonds',   label: 'Government bonds' },
  { key: 'house',   label: 'Property' },
  { key: 'gold',    label: 'Gold' },
  { key: 'deposit', label: 'Term deposit' },
  { key: 'savings', label: 'Savings account' },
];
const PRICES = { key: 'prices', label: 'Prices (inflation)' };
const CASH = { key: 'cash', label: 'Cash at home' };
function applyTheme() {
  const css = getComputedStyle(document.body);
  const [r, g, b] = (css.backgroundColor.match(/\d+/g) || [0, 0, 0]).map(Number);
  const pal = PALETTE[0.299 * r + 0.587 * g + 0.114 * b > 128 ? 'light' : 'dark'];
  ASSETS.forEach((a, i) => { a.color = pal[i]; });
  PRICES.color = css.getPropertyValue('--muted').trim() || '#9AA8C2';
  CASH.color = css.getPropertyValue('--line2').trim() || '#5E6B85';
}

// Every line starts at 100, so the value minus 100 is the total return in per cent.
const amount = 100;
let D = null, country = 'U2', years = 15, sortKey = 'name', sortDir = 1;

const isNum = v => typeof v === 'number' && isFinite(v);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (v, d = 1) => isNum(v) ? `${v > 0 ? '+' : ''}${v.toFixed(d)} %` : '—';
const rate = (v, d = 2) => isNum(v) ? `${v.toFixed(d)} %` : '—';
const cls = v => !isNum(v) ? '' : v > 0.05 ? 'up' : v < -0.05 ? 'down' : '';
const mIdx = m => +m.slice(0, 4) * 12 + +m.slice(5, 7) - 1;
const mStr = i => `${Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, '0')}`;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const mNice = m => m ? `${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}` : '';

// Series are stored as [first month, [values...]]; returns a lookup month -> value.
function series(code, key) {
  const a = D.assets[code]?.[key] || D.assets[D.countries[code].cur]?.[key];
  if (!a) return null;
  const [start, vals] = a, s0 = mIdx(start);
  return { first: s0, last: s0 + vals.length - 1, at: i => vals[i - s0] };
}

function render() {
  const c = D.countries[country];
  document.querySelectorAll('#region option').forEach(o => { o.selected = o.value === country; });
  renderNow(); renderCalc(); renderTable();
}

// ── Today: nominal and real yield per asset ──────────────────────────────
function renderNow() {
  const n = D.now.c[country] || {}, infl = n.inflation?.value, c = D.countries[country];
  document.getElementById('infl-line').innerHTML = isNum(infl)
    ? `Inflation in ${esc(c.name)}: <b>${rate(infl, 1)}</b> a year (${mNice(n.inflation.month)})${c.euro && D.now.dfr ? ` · ECB deposit rate ${rate(D.now.dfr.value)}` : ''}`
    : '';
  const cards = [
    ['savings', 'Savings account', n.savings, 'average rate on overnight deposits'],
    ['deposit', 'Term deposit', n.deposit1y, 'new deposits up to 1 year'],
    ['bonds', 'Government bond', n.bond10, '10-year yield'],
    ['stocks', 'Stocks', n.stocks_12m, 'EURO STOXX 50 incl. dividends, last 12 months'],
    ['gold', 'Gold', n.gold_12m, 'last 12 months'],
    ['house', 'Property', n.house_12m, 'house prices, last 12 months'],
  ];
  const color = k => ASSETS.find(a => a.key === k).color;
  document.getElementById('now').innerHTML = cards.map(([k, label, o, sub]) => {
    const v = o?.value, real = isNum(v) && isNum(infl) ? v - infl : null;
    return `<div class="i-tile">
      <div class="i-tile-head"><span class="i-dot" style="background:${color(k)}"></span>${label}</div>
      <div class="i-tile-real ${cls(real)}">${isNum(real) ? pct(real) : '—'}<span>real</span></div>
      <div class="i-tile-nom">${isNum(v) ? `${k === 'stocks' || k === 'gold' || k === 'house' ? pct(v) : rate(v)} before inflation` : 'no data for this country'}</div>
      <div class="i-tile-sub">${sub}${o?.month ? `, ${mNice(o.month)}` : ''}</div>
    </div>`;
  }).join('');
}

// ── Calculator: total return over N years ───────────────────────
function paths() {
  const all = [...ASSETS, PRICES].map(a => ({ ...a, s: series(country, a.key) })).filter(a => a.s);
  if (!all.length) return { list: [], from: 0, to: 0 };
  // The chart ends with the newest month any source has; each line stops at its own last month.
  const to = Math.max(...all.map(a => a.s.last)), from = to - years * 12;
  const list = all.filter(a => a.s.first <= from && a.s.last >= to - 6).map(a => {
    const base = a.s.at(from), pts = [];
    for (let i = from; i <= a.s.last; i++) { const v = a.s.at(i); if (isNum(v)) pts.push([i, amount * v / base]); }
    return { ...a, pts, final: pts[pts.length - 1][1], lastM: a.s.last };
  });
  return { list, from, to };
}

function renderCalc() {
  const c = D.countries[country], { list, from, to } = paths();
  document.getElementById('calc-title').textContent = `How much did each investment return over ${years} year${years > 1 ? 's' : ''}?`;
  document.getElementById('calc-sub').textContent = list.length ? `${c.name}, ${mNice(mStr(from))} to ${mNice(mStr(to))}, in ${c.cur}` : '';
  const prices = list.find(a => a.key === 'prices');
  const infl = prices ? prices.final / amount : null;
  const rows = list.filter(a => a.key !== 'prices').concat([{ ...CASH, final: amount, lastM: to }]);
  const yrs = l => (l - from) / 12;
  const pa = a => (Math.pow(a.final / amount, 1 / yrs(a.lastM)) - 1) * 100;
  const real = a => infl ? (Math.pow(a.final / amount / Math.pow(infl, yrs(a.lastM) / yrs(to)), 1 / yrs(a.lastM)) - 1) * 100 : null;
  rows.sort((a, b) => b.final - a.final);
  document.getElementById('rank').innerHTML = rows.map(a => `<tr>
      <td><span class="i-dot" style="background:${a.color}"></span>${a.label}${a.lastM < to ? `<span class="i-note"> to ${mNice(mStr(a.lastM))}</span>` : ''}</td>
      <td class="r m ${cls(a.final - amount)}">${ret(a.final)}</td>
      <td class="r m ${cls(pa(a))}">${pct(pa(a))}</td>
      <td class="r m ${cls(real(a))}">${pct(real(a))}</td></tr>`).join('')
    + (prices ? `<tr class="i-prices"><td><span class="i-dash"></span>Prices rose (inflation)</td><td class="r m">${ret(prices.final)}</td><td class="r m">${pct((Math.pow(infl, 1 / yrs(prices.lastM)) - 1) * 100)}</td><td class="r m"></td></tr>` : '');
  const missing = ASSETS.filter(a => !list.some(l => l.key === a.key)).map(a => a.label.toLowerCase());
  document.getElementById('calc-missing').textContent = missing.length
    ? `No data for ${c.name} over ${years} years: ${missing.join(', ')}.` : '';
  drawChart(list, from, to);
}

function drawChart(list, from, to) {
  const el = document.getElementById('chart');
  const W = Math.max(300, el.clientWidth), H = W < 520 ? 260 : 340;
  const pad = { l: 64, r: W < 520 ? 12 : 128, t: 12, b: 28 };
  const lines = [...list.filter(a => a.key !== 'prices'), ...list.filter(a => a.key === 'prices')];
  const ys = lines.flatMap(a => a.pts.map(p => p[1])).concat([amount]);
  let lo = Math.min(...ys), hi = Math.max(...ys);
  const span = hi - lo || amount * 0.1; lo -= span * 0.05; hi += span * 0.05;
  const x = i => pad.l + (i - from) / (to - from) * (W - pad.l - pad.r);
  const y = v => pad.t + (hi - v) / (hi - lo) * (H - pad.t - pad.b);
  const step = niceStep((hi - lo) / 5);
  let grid = '';
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step)
    grid += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" class="g"/><text x="${pad.l - 8}" y="${y(v) + 4}" class="ax" text-anchor="end">${axisPct(v)}</text>`;
  const yStep = years <= 3 ? 1 : years <= 5 ? 1 : years <= 10 ? 2 : 3;
  for (let yr = Math.ceil((from + 1) / 12); yr * 12 <= to; yr += yStep)
    grid += `<text x="${x(yr * 12)}" y="${H - 8}" class="ax" text-anchor="middle">${W < 520 && yStep === 1 && years > 3 ? `’${String(yr).slice(2)}` : yr}</text>`;
  const path = a => a.pts.map((p, j) => `${j ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
  const body = lines.map(a => `<path d="${path(a)}" class="ln${a.key === 'prices' ? ' dash' : ''}" stroke="${a.color}"/>`).join('');
  // Direct labels at the right end, nudged apart so they never overlap.
  let labels = '';
  if (pad.r > 60) {
    const ends = lines.map(a => ({ a, y: y(a.final) })).sort((p, q) => p.y - q.y);
    for (let j = 1; j < ends.length; j++) if (ends[j].y - ends[j - 1].y < 15) ends[j].y = ends[j - 1].y + 15;
    labels = ends.map(e => `<text x="${W - pad.r + 8}" y="${e.y + 4}" class="lb">${e.a.key === 'prices' ? 'Prices' : e.a.label}</text>`).join('');
  }
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${grid}
    <line x1="${pad.l}" x2="${W - pad.r}" y1="${y(amount)}" y2="${y(amount)}" class="base"/>${body}${labels}
    <line class="xh" id="xh" y1="${pad.t}" y2="${H - pad.b}" visibility="hidden"/><g id="dots"></g>
    <rect x="${pad.l}" y="0" width="${W - pad.l - pad.r}" height="${H}" fill="transparent" id="hit"/></svg>`;
  document.getElementById('legend').innerHTML = lines.map(a =>
    `<span><i class="${a.key === 'prices' ? 'dash' : ''}" style="background:${a.color}"></i>${a.label}</span>`).join('')
    + `<span><i class="base"></i>0 % (no gain)</span>`;

  const hit = document.getElementById('hit'), tip = document.getElementById('tip'), xh = document.getElementById('xh'), dots = document.getElementById('dots');
  const move = ev => {
    const r = hit.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    const i = Math.round(from + px / r.width * (to - from));
    if (i < from || i > to) return;
    const vals = lines.map(a => ({ a, p: a.pts.find(p => p[0] === i) })).filter(v => v.p).sort((p, q) => q.p[1] - p.p[1]);
    xh.setAttribute('x1', x(i)); xh.setAttribute('x2', x(i)); xh.setAttribute('visibility', 'visible');
    dots.innerHTML = vals.map(v => `<circle cx="${x(i)}" cy="${y(v.p[1])}" r="4.5" fill="${v.a.color}" class="dt"/>`).join('');
    tip.innerHTML = `<b>${mNice(mStr(i))}</b>` + vals.map(v => `<div><i style="background:${v.a.color}"></i>${v.a.key === 'prices' ? 'Prices' : v.a.label}<span>${ret(v.p[1])}</span></div>`).join('');
    tip.hidden = false;
    const wrap = el.parentElement.getBoundingClientRect(), tx = r.left - wrap.left + px;
    tip.style.left = `${Math.min(Math.max(tx + 14, 0), wrap.width - tip.offsetWidth)}px`;
    if (tx + 14 + tip.offsetWidth > wrap.width) tip.style.left = `${Math.max(0, tx - 14 - tip.offsetWidth)}px`;
  };
  const leave = () => { tip.hidden = true; xh.setAttribute('visibility', 'hidden'); dots.innerHTML = ''; };
  hit.addEventListener('mousemove', move); hit.addEventListener('touchmove', move, { passive: true });
  hit.addEventListener('touchstart', move, { passive: true });
  hit.addEventListener('mouseleave', leave); hit.addEventListener('touchend', leave);
}
const niceStep = s => { const p = Math.pow(10, Math.floor(Math.log10(s))), f = s / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; };
const ret = v => pct(v - amount, Math.abs(v - amount) >= 100 ? 0 : 1);
const axisPct = v => `${Math.round(v - amount) > 0 ? '+' : ''}${Math.round(v - amount)} %`;

// ── All of Europe side by side ──────────────────────────────────────────
const COLS = [
  { key: 'name', label: 'Country', left: true },
  { key: 'inflation', label: 'Inflation' },
  { key: 'savings', label: 'Savings acc.' },
  { key: 'deposit1y', label: 'Term deposit' },
  { key: 'realdep', label: 'Deposit, real' },
  { key: 'bond10', label: '10y bond' },
  { key: 'realbond', label: 'Bond, real' },
  { key: 'house_12m', label: 'Property 12m' },
];
function tableRows() {
  return Object.entries(D.countries).map(([code, c]) => {
    const n = D.now.c[code] || {}, v = k => n[k]?.value;
    const infl = v('inflation');
    return { code, name: c.name, euro: c.euro, cur: c.cur, inflation: infl, savings: v('savings'), deposit1y: v('deposit1y'),
      realdep: isNum(v('deposit1y')) && isNum(infl) ? v('deposit1y') - infl : null,
      bond10: v('bond10'), realbond: isNum(v('bond10')) && isNum(infl) ? v('bond10') - infl : null, house_12m: v('house_12m') };
  });
}
function renderTable() {
  const rows = tableRows().sort((a, b) => {
    if (a.code === 'U2' || b.code === 'U2') return a.code === 'U2' ? -1 : 1;
    const p = a[sortKey], q = b[sortKey];
    if (sortKey === 'name') return sortDir * p.localeCompare(q);
    if (!isNum(p)) return 1; if (!isNum(q)) return -1;
    return sortDir * (p - q);
  });
  document.getElementById('eu-head').innerHTML = `<tr>${COLS.map(c => `<th class="${c.left ? '' : 'r'} ${c.key === sortKey ? 'on' : ''}" data-k="${c.key}" aria-sort="${c.key === sortKey ? (sortDir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button">${c.label}${c.key === sortKey ? (sortDir > 0 ? ' ▲' : ' ▼') : ''}</button></th>`).join('')}</tr>`;
  document.getElementById('eu-body').innerHTML = rows.map(r => `<tr class="${r.code === country ? 'sel' : ''} ${r.code === 'U2' ? 'agg' : ''}" data-c="${r.code}">
    <td><a href="#calc" data-c="${r.code}">${esc(r.name)}</a>${r.euro ? '' : `<span class="i-note"> ${r.cur}</span>`}</td>
    <td class="r m">${rate(r.inflation, 1)}</td><td class="r m">${rate(r.savings)}</td><td class="r m">${rate(r.deposit1y)}</td>
    <td class="r m ${cls(r.realdep)}">${pct(r.realdep)}</td><td class="r m">${rate(r.bond10)}</td>
    <td class="r m ${cls(r.realbond)}">${pct(r.realbond)}</td><td class="r m ${cls(r.house_12m)}">${pct(r.house_12m)}</td></tr>`).join('');
}

function setup() {
  const sel = document.getElementById('region'), groups = { true: [], false: [] };
  Object.entries(D.countries).sort((a, b) => a[0] === 'U2' ? -1 : b[0] === 'U2' ? 1 : a[1].name.localeCompare(b[1].name))
    .forEach(([code, c]) => groups[c.euro].push(`<option value="${code}">${esc(c.name)}</option>`));
  sel.innerHTML = `<optgroup label="Euro">${groups.true.join('')}</optgroup>` + (groups.false.length ? `<optgroup label="Other currencies">${groups.false.join('')}</optgroup>` : '');
  sel.addEventListener('change', () => { country = sel.value; save(); render(); });
  document.querySelectorAll('#years button').forEach(b => b.addEventListener('click', () => {
    years = +b.dataset.years; document.querySelectorAll('#years button').forEach(x => x.classList.toggle('on', x === b)); renderCalc();
  }));
  document.getElementById('eu-head').addEventListener('click', e => {
    const th = e.target.closest('th'); if (!th) return;
    const k = th.dataset.k; sortDir = k === sortKey ? -sortDir : (k === 'name' ? 1 : -1); sortKey = k; renderTable();
  });
  document.getElementById('eu-body').addEventListener('click', e => {
    const tr = e.target.closest('tr[data-c]'); if (!tr) return;
    e.preventDefault(); country = tr.dataset.c; save(); render();
    document.getElementById('calc').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(renderCalc, 150); });
  document.getElementById('updated').textContent = `Data updated ${D.updated.slice(0, 10)}`;
  document.getElementById('sources').innerHTML = D.sources.map(([n, u, what]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a>: ${esc(what)}</li>`).join('');
}
function save() { try { localStorage.setItem('finila-invest-country', country); } catch (e) { /* private mode */ } }

fetch('js/invest.json', { cache: 'no-cache' }).then(r => r.json()).then(d => {
  D = d;
  applyTheme();
  let saved = null; try { saved = localStorage.getItem('finila-invest-country'); } catch (e) { /* private mode */ }
  const hash = location.hash.slice(1).toUpperCase();
  country = D.countries[hash] ? hash : D.countries[saved] ? saved : 'U2';
  setup(); render();
}).catch(() => { document.getElementById('now').innerHTML = '<p class="i-sub">Data could not be loaded. Please try again later.</p>'; });
