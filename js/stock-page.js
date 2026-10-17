// Company page (/stock/<name>): the page is rebuilt once a day, so the newest delayed price
// from js/company-prices.json (refreshed hourly) replaces the one written into the page.
(async function () {
  const box = document.querySelector('.sp-price[data-isin]');
  if (!box) return;
  let data;
  try { data = await (await fetch('/js/company-prices.json', { cache: 'no-cache' })).json(); } catch { return; }
  const q = data.rows[box.dataset.isin];
  if (!q) return;
  const [price, change, venue, day, final] = ['price', 'change', 'venue', 'date', 'final'].map(f => q[data.fields.indexOf(f)]);
  const fmt = (v, d) => v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
  box.querySelector('[data-f=price]').textContent = '€' + fmt(price, 2);
  const ch = box.querySelector('[data-f=change]');
  ch.textContent = typeof change === 'number' ? (change >= 0 ? '+' : '') + fmt(change, 2) + '%' : '';
  ch.className = 'modal-change ' + (change >= 0 ? 'pos' : 'neg');
  box.querySelector('[data-f=badge]').textContent = `Real price · ${venue} · ${day}${final ? '' : ' · 15 min delayed'}`;
})();

// Price chart: the range buttons redraw the line from the closes embedded in the page,
// and moving over the chart shows the close of that day.
(function () {
  const fig = document.querySelector('.sp-chart');
  const data = fig && fig.querySelector('.sp-hist');
  if (!data) return;
  const all = JSON.parse(data.textContent);
  const svg = fig.querySelector('svg'), line = svg.querySelector('polyline'), area = svg.querySelector('polygon');
  const cap = fig.querySelectorAll('figcaption span'), axis = fig.querySelectorAll('.sp-chart-axis span');
  const W = 600, H = 150, P = 4;
  const fmt = (v, d = 2) => v.toLocaleString('en-GB', { minimumFractionDigits: d, maximumFractionDigits: d });
  let pts = all, xy = [];
  function draw(days) {
    const from = days ? new Date(new Date(all[all.length - 1][0]).getTime() - days * 864e5).toISOString().slice(0, 10) : '';
    pts = all.filter(p => p[0] >= from);
    if (pts.length < 2) pts = all.slice(-2);
    const vals = pts.map(p => p[1]), lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
    xy = vals.map((v, i) => [P + i * (W - 2 * P) / (vals.length - 1), P + (hi - v) * (H - 2 * P) / span]);
    const pl = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    const chg = (vals[vals.length - 1] / vals[0] - 1) * 100, cls = chg >= 0 ? 'pos' : 'neg';
    line.setAttribute('points', pl); line.setAttribute('class', 'sp-chart-line ' + cls);
    area.setAttribute('points', `${P},${H} ${pl} ${W - P},${H}`); area.setAttribute('class', 'sp-chart-area ' + cls);
    cap[0].textContent = 'Price since ' + pts[0][0];
    cap[1].textContent = (chg >= 0 ? '+' : '') + fmt(chg, 1) + '%'; cap[1].className = cls;
    axis[0].textContent = pts[0][0]; axis[1].textContent = `low €${fmt(lo)} · high €${fmt(hi)}`; axis[2].textContent = pts[pts.length - 1][0];
  }
  fig.querySelectorAll('[data-days]').forEach(b => b.addEventListener('click', () => {
    fig.querySelectorAll('[data-days]').forEach(x => x.classList.toggle('active', x === b));
    draw(Number(b.dataset.days));
  }));
  const dot = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  dot.setAttribute('class', 'sp-chart-cursor'); dot.setAttribute('y1', 0); dot.setAttribute('y2', H); dot.style.display = 'none';
  svg.appendChild(dot);
  const tip = document.createElement('div'); tip.className = 'sp-chart-tip'; fig.appendChild(tip);
  svg.addEventListener('pointermove', e => {
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(pts.length - 1, Math.round((x - P) / (W - 2 * P) * (pts.length - 1))));
    dot.setAttribute('x1', xy[i][0]); dot.setAttribute('x2', xy[i][0]); dot.style.display = '';
    tip.textContent = `${pts[i][0]} · €${fmt(pts[i][1])}`; tip.style.display = 'block';
    tip.style.left = Math.min(r.width - tip.offsetWidth, Math.max(0, xy[i][0] / W * r.width - tip.offsetWidth / 2)) + 'px';
  });
  svg.addEventListener('pointerleave', () => { dot.style.display = 'none'; tip.style.display = 'none'; });
  draw(0);
})();
