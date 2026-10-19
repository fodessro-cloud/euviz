// FINILA "Interest rates": Euribor, euro area government bond yields and term deposit rates on one
// chart. Data: js/rates.json, built daily by scripts/data/rates.py from the ECB Data Portal.

// One colour family per kind of rate, light to dark with the length of the period.
const COLORS = {
  eur1m: '#9CC3F5', eur3m: '#5B9BFF', eur6m: '#2A78D6', eur12m: '#14427E',
  gov2y: '#F5B38F', gov5y: '#EB6834', gov10y: '#A8401A',
  aaa10y: '#1BAF7A', corp: '#8E44AD', dep1y: '#C98500',
};
let D = null, years = 10;
const hidden = new Set();

const isNum = v => typeof v === 'number' && isFinite(v);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const rate = (v, d = 2) => isNum(v) ? `${v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d })} %` : '—';
const mIdx = m => +m.slice(0, 4) * 12 + +m.slice(5, 7) - 1;
const mStr = i => `${Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, '0')}`;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const mNice = m => m ? `${MONTHS[+m.slice(5, 7) - 1]} ${m.slice(0, 4)}` : '';
const dNice = d => d.length === 7 ? mNice(d) : new Date(d + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const niceStep = s => { const p = Math.pow(10, Math.floor(Math.log10(s))), f = s / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; };

function renderNow() {
  document.getElementById('now').innerHTML = D.series.map(s => `<div class="i-tile">
    <div class="i-tile-head"><span class="i-dot" style="background:${COLORS[s.key]}"></span>${esc(s.label)}</div>
    <div class="i-tile-real">${rate(s.latest.value)}</div>
    <div class="i-tile-sub">${s.latest.date.length === 7 ? 'average in ' : ''}${dNice(s.latest.date)}</div></div>`).join('');
}

function renderChart() {
  const el = document.getElementById('chart');
  const all = D.series.map(s => ({ ...s, color: COLORS[s.key], s0: mIdx(s.first) }));
  const end = Math.max(...all.map(a => a.s0 + a.values.length - 1));
  const from = years ? end - years * 12 : Math.min(...all.map(a => a.s0));
  const lines = all.filter(a => !hidden.has(a.key)).map(a => {
    const pts = a.values.map((v, j) => [a.s0 + j, v]).filter(p => p[0] >= from && isNum(p[1]));
    return { ...a, pts, final: pts.length ? pts[pts.length - 1][1] : null };
  }).filter(a => a.pts.length);
  document.getElementById('legend').innerHTML = all.map(a => `<button type="button" data-k="${a.key}" class="${hidden.has(a.key) ? 'off' : ''}" aria-pressed="${!hidden.has(a.key)}"><i style="background:${a.color}"></i>${esc(a.label)}</button>`).join('');

  const W = Math.max(300, el.clientWidth), H = W < 520 ? 280 : 380;
  const pad = { l: 52, r: W < 520 ? 12 : 168, t: 12, b: 28 };
  const ys = lines.flatMap(a => a.pts.map(p => p[1])).concat([0]);
  let lo = Math.min(...ys), hi = Math.max(...ys);
  const span = hi - lo || 1; lo -= span * 0.05; hi += span * 0.05;
  const x = i => pad.l + (i - from) / Math.max(1, end - from) * (W - pad.l - pad.r);
  const y = v => pad.t + (hi - v) / (hi - lo) * (H - pad.t - pad.b);
  const step = niceStep((hi - lo) / 5);
  let grid = '';
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step)
    grid += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(v)}" y2="${y(v)}" class="g"/><text x="${pad.l - 8}" y="${y(v) + 4}" class="ax" text-anchor="end">${+v.toFixed(2)} %</text>`;
  const yrs = (end - from) / 12, yStep = yrs <= 5 ? 1 : yrs <= 10 ? 2 : yrs <= 20 ? 4 : 5;
  for (let yr = Math.ceil((from + 1) / 12); yr * 12 <= end; yr += yStep)
    grid += `<text x="${x(yr * 12)}" y="${H - 8}" class="ax" text-anchor="middle">${W < 520 && yrs > 5 ? `’${String(yr).slice(2)}` : yr}</text>`;
  if (yrs <= 1) grid += `<text x="${x(from)}" y="${H - 8}" class="ax">${mNice(mStr(from))}</text>`;
  const path = a => a.pts.map((p, j) => `${j && a.pts[j - 1][0] === p[0] - 1 ? 'L' : 'M'}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('');
  const body = lines.map(a => `<path d="${path(a)}" class="ln" stroke="${a.color}"/>`).join('');
  // Direct labels at the right end, nudged apart so they never overlap.
  let labels = '';
  if (pad.r > 60) {
    const ends = lines.map(a => ({ a, y: y(a.final) })).sort((p, q) => p.y - q.y);
    for (let j = 1; j < ends.length; j++) if (ends[j].y - ends[j - 1].y < 15) ends[j].y = ends[j - 1].y + 15;
    labels = ends.map(e => `<text x="${W - pad.r + 8}" y="${e.y + 4}" class="lb">${esc(e.a.label.replace('Government bonds', 'Gov.').replace('AAA government bonds', 'AAA gov.').replace(' up to 1 year', '').replace('Corporate bonds (German firms)', 'Corporate (DE)'))}</text>`).join('');
  }
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${grid}
    ${lo < 0 ? `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y(0)}" y2="${y(0)}" class="base"/>` : ''}${body}${labels}
    <line class="xh" id="xh" y1="${pad.t}" y2="${H - pad.b}" visibility="hidden"/><g id="dots"></g>
    <rect x="${pad.l}" y="0" width="${W - pad.l - pad.r}" height="${H}" fill="transparent" id="hit"/></svg>`;

  const hit = document.getElementById('hit'), tip = document.getElementById('tip'), xh = document.getElementById('xh'), dots = document.getElementById('dots');
  const move = ev => {
    const r = hit.getBoundingClientRect(), px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    const i = Math.round(from + px / r.width * (end - from));
    if (i < from || i > end) return;
    const vals = lines.map(a => ({ a, p: a.pts.find(p => p[0] === i) })).filter(v => v.p).sort((p, q) => q.p[1] - p.p[1]);
    xh.setAttribute('x1', x(i)); xh.setAttribute('x2', x(i)); xh.setAttribute('visibility', 'visible');
    dots.innerHTML = vals.map(v => `<circle cx="${x(i)}" cy="${y(v.p[1])}" r="4.5" fill="${v.a.color}" class="dt"/>`).join('');
    tip.innerHTML = `<b>${mNice(mStr(i))}</b>` + vals.map(v => `<div><i style="background:${v.a.color}"></i>${esc(v.a.label)}<span>${rate(v.p[1])}</span></div>`).join('');
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

function setup() {
  document.querySelectorAll('#years button').forEach(b => b.addEventListener('click', () => {
    years = +b.dataset.years; document.querySelectorAll('#years button').forEach(x => x.classList.toggle('on', x === b)); renderChart();
  }));
  document.getElementById('legend').addEventListener('click', e => {
    const b = e.target.closest('button[data-k]'); if (!b) return;
    hidden.has(b.dataset.k) ? hidden.delete(b.dataset.k) : hidden.add(b.dataset.k);
    if (hidden.size === D.series.length) hidden.delete(b.dataset.k);   // keep at least one line
    renderChart();
  });
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(renderChart, 150); });
  document.getElementById('updated').textContent = `Data updated ${D.updated.slice(0, 10)}`;
  document.getElementById('sources').innerHTML = D.sources.map(([n, u, what]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a>: ${esc(what)}</li>`).join('');
  if (D.failed.length) document.getElementById('failed').textContent = `Not refreshed today: ${D.failed.join(', ')} (shown from the previous update).`;
}

fetch('js/rates.json', { cache: 'no-cache' }).then(r => r.json()).then(d => {
  D = d; setup(); renderNow(); renderChart();
}).catch(() => { document.getElementById('now').innerHTML = '<p class="i-sub">Data could not be loaded. Please try again later.</p>'; });
