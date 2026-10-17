// FINILA homepage: renders the data blocks from js/data.js

const fmt = (n, d = 2) => Number(n).toLocaleString('sk-SK', { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = n => (n >= 0 ? '+' : '−') + fmt(Math.abs(n)) + ' %';
const dir = n => (n >= 0 ? 'up' : 'down');
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const stockLink = t => `screener.html?stock=${encodeURIComponent(t)}`;

const COUNTRY_SK = {
  Austria: 'Rakúsko', Belgium: 'Belgicko', Denmark: 'Dánsko', Finland: 'Fínsko', France: 'Francúzsko',
  Germany: 'Nemecko', Ireland: 'Írsko', Italy: 'Taliansko', Netherlands: 'Holandsko', Norway: 'Nórsko',
  Poland: 'Poľsko', Portugal: 'Portugalsko', Spain: 'Španielsko', Sweden: 'Švédsko',
  Switzerland: 'Švajčiarsko', UK: 'Veľká Británia'
};
const SECTOR_SK = {
  Finance: 'Financie', 'Consumer Cyclical': 'Cyklická spotreba', Healthcare: 'Zdravotníctvo',
  'Consumer Defensive': 'Základná spotreba', Technology: 'Technológie', Energy: 'Energie',
  Industrials: 'Priemysel', Materials: 'Suroviny', Utilities: 'Utility', Communication: 'Telekomunikácie'
};

// ── Ticker bar + index cards ──────────────────────
function renderIndices() {
  document.getElementById('ticker').innerHTML = INDICES.map(i =>
    `<span><span class="name">${i.name}</span>${fmt(i.value)}<span class="chg ${dir(i.change)}">${pct(i.change)}</span></span>`
  ).join('');
  document.getElementById('index-cards').innerHTML = INDICES.slice(0, 6).map(i =>
    `<a href="groups.html"><span class="name">${i.name} · ${COUNTRY_SK[i.country] || i.country}</span>
      <span class="val">${fmt(i.value)}</span><span class="chg ${dir(i.change)}">${pct(i.change)}</span></a>`
  ).join('');
}

// ── Sector map: market-cap weighted average change ─
function tileColor(c) {
  if (c >= 1)    return '#34C38F';
  if (c >= 0.4)  return '#7EDDB4';
  if (c >= 0)    return '#B9EBD3';
  if (c > -0.4)  return '#FFB3B3';
  if (c > -1)    return '#FF8A8A';
  return '#FF6060';
}
function renderSectorMap() {
  const bySector = {};
  STOCKS.forEach(s => {
    const g = bySector[s.sector] || (bySector[s.sector] = { cap: 0, w: 0 });
    g.cap += s.marketCap;
    g.w += s.marketCap * s.change;
  });
  const sectors = Object.entries(bySector)
    .map(([name, g]) => ({ name, cap: g.cap, change: g.w / g.cap }))
    .sort((a, b) => b.cap - a.cap);
  const sizes = ['big', 'big', 'mid', 'mid', 'mid'];
  document.getElementById('sector-map').innerHTML = sectors.map((s, i) => {
    const size = sizes[i] || 'sm';
    return `<a class="${size} ${s.change < 0 ? 'neg' : ''}" href="map.html" style="background:${tileColor(s.change)}">
      ${SECTOR_SK[s.name] || s.name}<span>${pct(s.change)}</span></a>`;
  }).join('');
}

// ── Value-investor presets ────────────────────────
const PRESETS = [
  { id: 'buffett', title: 'Buffettov filter', rule: 'ROE nad 15 %, dlh / vlastné imanie pod 0,5 a rastúci zisk',
    test: s => s.roe > 15 && s.de < 0.5 && s.epsGrowth > 0, sort: (a, b) => b.roe - a.roe,
    metric: s => `ROE ${fmt(s.roe, 1)} %` },
  { id: 'cheap', title: 'Lacné firmy', rule: 'P/E pod 10 a cena pod 1,5-násobkom účtovnej hodnoty',
    test: s => s.pe && s.pe < 10 && s.pb < 1.5, sort: (a, b) => a.pe - b.pe,
    metric: s => `P/E ${fmt(s.pe, 1)}` },
  { id: 'dividend', title: 'Dividendové firmy', rule: 'Dividenda nad 4 % a P/E pod 15, aby výplata mala z čoho byť',
    test: s => s.dividend >= 4 && s.pe && s.pe < 15, sort: (a, b) => b.dividend - a.dividend,
    metric: s => `Div. ${fmt(s.dividend, 1)} %` }
];
function renderPresets() {
  document.getElementById('presets').innerHTML = PRESETS.map(p => {
    const hits = STOCKS.filter(p.test).sort(p.sort);
    const rows = hits.slice(0, 5).map(s =>
      `<li><span><a href="${stockLink(s.ticker)}">${esc(s.ticker)}</a><span class="nm">${esc(s.name)}</span></span><span class="metric">${p.metric(s)}</span></li>`
    ).join('');
    return `<article class="h-card h-preset" id="preset-${p.id}">
      <div><h3>${p.title}</h3><p class="rule">${p.rule}</p></div>
      <ul>${rows}</ul>
      <a class="more" href="screener.html">Všetkých ${hits.length} výsledkov v screeneri</a>
    </article>`;
  }).join('');
  document.querySelectorAll('[data-preset]').forEach(chip => chip.addEventListener('click', () => {
    const card = document.getElementById('preset-' + chip.dataset.preset);
    card.classList.add('flash');
    setTimeout(() => card.classList.remove('flash'), 1500);
  }));
}

// ── Investment comparison (illustrative figures) ──
const COMPARE = {
  5:  [['Akcie EÚ (STOXX 600)', 14800], ['Akcie USA (S&P 500)', 19200], ['Zlato', 17600], ['Byt na Slovensku', 13900], ['Dlhopisy EÚ', 9600], ['Termínovaný vklad', 10500], ['Hotovosť po inflácii', 7900]],
  10: [['Akcie EÚ (STOXX 600)', 19500], ['Akcie USA (S&P 500)', 33000], ['Zlato', 24000], ['Byt na Slovensku', 18000], ['Dlhopisy EÚ', 10800], ['Termínovaný vklad', 11000], ['Hotovosť po inflácii', 7400]],
  20: [['Akcie EÚ (STOXX 600)', 31000], ['Akcie USA (S&P 500)', 64000], ['Zlato', 52000], ['Byt na Slovensku', 34000], ['Dlhopisy EÚ', 15800], ['Termínovaný vklad', 13200], ['Hotovosť po inflácii', 6100]]
};
const BAR_COLORS = ['#5B9BFF', '#8DB8FF', '#F2B33D', '#C89BFF', '#6FD6E8', '#B4C0D6', '#FF7A7A'];
function renderCompare(years) {
  const rows = COMPARE[years];
  const max = Math.max(...rows.map(r => r[1]));
  document.getElementById('compare').innerHTML = rows.map(([label, v], i) =>
    `<div class="h-bar"><span class="label">${label}</span>
      <div class="track"><div class="fill" style="width:${Math.max(4, Math.round(v / max * 100))}%;background:${BAR_COLORS[i]}"></div></div>
      <span class="val">${fmt(v, 0)} €</span></div>`
  ).join('');
  document.querySelectorAll('#periods button').forEach(b => b.classList.toggle('on', Number(b.dataset.years) === years));
}

// ── Movers table ──────────────────────────────────
function renderMovers(tab) {
  const list = [...STOCKS];
  if (tab === 'up') list.sort((a, b) => b.change - a.change);
  if (tab === 'down') list.sort((a, b) => a.change - b.change);
  if (tab === 'vol') list.sort((a, b) => b.volume * b.price - a.volume * a.price);
  document.getElementById('movers').innerHTML = list.slice(0, 8).map(s =>
    `<tr><td><a href="${stockLink(s.ticker)}">${esc(s.ticker)}</a></td><td>${esc(s.name)}</td>
      <td class="c">${COUNTRY_SK[s.country] || s.country}</td>
      <td class="r m">${fmt(s.price)}</td><td class="r m ${dir(s.change)}">${pct(s.change)}</td>
      <td class="r m c">${s.pe ? fmt(s.pe, 1) : '—'}</td></tr>`
  ).join('');
  document.querySelectorAll('#tabs button').forEach(b => {
    const on = b.dataset.tab === tab;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', on);
  });
}

// ── Search: a known ticker or name opens its detail in the screener ─
function setupSearch() {
  document.getElementById('stock-list').innerHTML = STOCKS.map(s => `<option value="${esc(s.ticker)}">${esc(s.name)}</option>`).join('');
  document.querySelector('.h-search').addEventListener('submit', e => {
    e.preventDefault();
    const q = document.getElementById('q').value.trim().toLowerCase();
    if (!q) { location.href = 'screener.html'; return; }
    const hit = STOCKS.find(s => s.ticker.toLowerCase() === q)
      || STOCKS.find(s => s.name.toLowerCase().includes(q));
    location.href = hit ? stockLink(hit.ticker) : 'screener.html';
  });
}

document.addEventListener('DOMContentLoaded', () => {
  renderIndices();
  renderSectorMap();
  renderPresets();
  renderCompare(10);
  renderMovers('up');
  setupSearch();
  document.querySelectorAll('#periods button').forEach(b => b.addEventListener('click', () => renderCompare(Number(b.dataset.years))));
  document.querySelectorAll('#tabs button').forEach(b => b.addEventListener('click', () => renderMovers(b.dataset.tab)));
});
