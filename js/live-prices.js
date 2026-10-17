// Puts the real prices from Deutsche Börse (js/prices.js) into the stock list from js/data.js.
// Load after both files and before the page's own script. Stocks without a real price stay illustrative.
(function () {
  if (typeof PRICES === 'undefined' || typeof STOCKS === 'undefined') return;
  let real = 0, live = false;
  for (const s of STOCKS) {
    const p = PRICES[`${s.ticker}@${s.country}`];
    if (!p) continue;
    s.price = p.price;
    // Until a previous close is known the change is shown as "-" and counts as 0 in averages and the map.
    s.changeKnown = p.change !== null;
    s.change = p.change ?? 0;
    s.volume = p.volume;
    s.high52 = Math.max(s.high52, p.price);
    s.low52 = Math.min(s.low52, p.price);
    s.realPrice = p;
    real++;
    if (!p.final) live = true;
  }
  if (!real) return;
  const day = new Date(PRICES_DATE + 'T12:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const text = `FINILA preview: prices of ${real} of ${STOCKS.length} stocks are real ` +
    (live ? `(${day}, 15 minutes delayed)` : `(closing prices of ${day})`) +
    ', from Deutsche Börse (Xetra, Börse Frankfurt). All other figures are illustrative. Not investment advice.';
  const show = () => document.querySelectorAll('.demo-banner').forEach(b => { b.textContent = text; });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', show);
  else show();
})();

// "Xetra · 16 Oct, 17:35 CET" for a stock with a real price, '' otherwise.
function realPriceLabel(s) {
  const p = s.realPrice;
  if (!p) return '';
  const at = new Date(`${p.date}T${p.time}:00Z`);
  const when = at.toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });
  return `${p.venue} · ${when} ${p.final ? 'last trade' : '(15 min delayed)'}`;
}
