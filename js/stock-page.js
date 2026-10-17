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
