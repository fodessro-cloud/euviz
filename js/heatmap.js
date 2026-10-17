// Squarified treemap for market heat map

let hmGroupBy = 'sector';
let hmSize    = 'marketCap';
let hmColor   = 'change';

function getHmValue(stock) {
  const v = stock[hmColor];
  return v ?? 0;
}

function colorFromChange(val) {
  // -5% → deep red, 0 → neutral, +5% → deep green
  const v = Math.max(-5, Math.min(5, val));
  if (v >= 0) {
    const t = v / 5;
    const r = Math.round(22 + (34 - 22) * t);
    const g = Math.round(197 - (197 - 80) * (1 - t));
    const b = Math.round(94 - (94 - 20) * t);
    return `rgb(${r},${g},${b})`;
  } else {
    const t = Math.abs(v) / 5;
    const r = Math.round(239 - (239 - 120) * (1 - t));
    const g = Math.round(68 - (68 - 20) * t);
    const b = Math.round(68 - (68 - 20) * t);
    return `rgb(${r},${g},${b})`;
  }
}

// Squarify algorithm
function squarify(items, rect) {
  if (!items.length) return [];
  const total = items.reduce((s, i) => s + i.value, 0);
  const area  = rect.w * rect.h;
  const scale = area / total;

  const result = [];
  let remaining = [...items];
  let { x, y, w, h } = rect;

  while (remaining.length) {
    const row = [];
    let rowSum = 0;
    const side = Math.min(w, h);

    for (const item of remaining) {
      const testRow = [...row, item];
      const testSum = rowSum + item.value * scale;
      const worst1 = worstRatio(row,    rowSum,         side);
      const worst2 = worstRatio(testRow, testSum,       side);
      if (row.length && worst2 > worst1) break;
      row.push(item);
      rowSum += item.value * scale;
    }

    remaining = remaining.slice(row.length);
    const rowLen = rowSum / side;

    // Wide area: the row is a column on the left; tall area: a row on top
    let pos = (w >= h) ? y : x;
    for (const item of row) {
      const size = (item.value * scale) / rowLen;
      let rx, ry, rw, rh;
      if (w >= h) { rx = x;   ry = pos; rw = rowLen; rh = size; }
      else         { rx = pos; ry = y;   rw = size;   rh = rowLen; }
      result.push({ ...item, rect: { x: rx, y: ry, w: rw, h: rh } });
      pos += size;
    }

    if (w >= h) { x += rowLen; w -= rowLen; }
    else         { y += rowLen; h -= rowLen; }
  }
  return result;
}

function worstRatio(row, rowSum, side) {
  if (!row.length) return Infinity;
  const max = Math.max(...row.map(i => i.value));
  const min = Math.min(...row.map(i => i.value));
  const s2 = side * side;
  const rs2 = rowSum * rowSum;
  return Math.max((s2 * max) / rs2, rs2 / (s2 * min));
}

function renderHeatmap() {
  const canvas = document.getElementById('heatmap-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const W = canvas.offsetWidth;
  const H = canvas.offsetHeight;
  canvas.width  = W;
  canvas.height = H;

  ctx.clearRect(0, 0, W, H);

  // Group stocks
  const groups = {};
  for (const s of STOCKS) {
    const g = s[hmGroupBy] || 'Other';
    if (!groups[g]) groups[g] = [];
    groups[g].push(s);
  }

  // Build top-level items (groups)
  const groupItems = Object.entries(groups).map(([name, stocks]) => ({
    name,
    value: stocks.reduce((s, st) => s + st.marketCap, 0),
    stocks,
  })).sort((a, b) => b.value - a.value);

  // Layout groups
  const PAD = 4;
  const groupRects = squarify(groupItems, { x: PAD, y: PAD, w: W - PAD*2, h: H - PAD*2 });

  const allTiles = [];
  for (const gr of groupRects) {
    const { x, y, w, h } = gr.rect;

    // Group header
    ctx.fillStyle = '#F6F8FB';
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);

    const HEADER = h > 40 ? 22 : 0;

    if (HEADER) {
      ctx.fillStyle = '#E3E9F3';
      ctx.fillRect(x, y, w, HEADER);
      ctx.fillStyle = '#34445F';
      ctx.font = `bold ${Math.min(11, w/8)}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      ctx.fillText(gr.name, x + w/2, y + HEADER - 6);
    }

    // Layout stocks within group
    const stockItems = gr.stocks.map(s => ({
      ...s,
      value: s[hmSize] || 1,
    })).sort((a, b) => b.value - a.value);

    const inner = { x: x + 2, y: y + HEADER + 2, w: w - 4, h: h - HEADER - 4 };
    if (inner.w < 4 || inner.h < 4) continue;
    const tileRects = squarify(stockItems, inner);
    allTiles.push(...tileRects);

    for (const tile of tileRects) {
      const { x: tx, y: ty, w: tw, h: th } = tile.rect;
      if (tw < 2 || th < 2) continue;

      const val = getHmValue(tile);
      ctx.fillStyle = colorFromChange(val);
      ctx.fillRect(tx + 1, ty + 1, tw - 2, th - 2);

      // Ticker label
      if (tw > 28 && th > 18) {
        const fs = Math.min(14, tw / 4, th / 2.5);
        ctx.fillStyle = 'rgba(255,255,255,0.92)';
        ctx.font = `bold ${fs}px Inter, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(tile.ticker, tx + tw/2, ty + th/2 - (th > 40 ? 8 : 0));

        if (th > 40) {
          ctx.font = `${Math.max(9, fs - 3)}px Inter, sans-serif`;
          ctx.fillStyle = 'rgba(255,255,255,0.72)';
          const sign = val >= 0 ? '+' : '';
          const label = hmColor === 'change' && tile.changeKnown === false ? '-' : `${sign}${val.toFixed(2)}%`;
          ctx.fillText(label, tx + tw/2, ty + th/2 + fs * 0.9);
        }
      }
    }
  }

  // Tooltip hit areas
  canvas._tileRects = allTiles;
}

function initHeatmap() {
  const canvas = document.getElementById('heatmap-canvas');
  if (!canvas) return;

  const tooltip = document.getElementById('hm-tooltip');

  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    if (!canvas._tileRects) return;
    const hit = canvas._tileRects.find(t => {
      const r = t.rect;
      return mx >= r.x && mx <= r.x + r.w && my >= r.y && my <= r.y + r.h;
    });

    if (hit && tooltip) {
      tooltip.style.display = 'block';
      tooltip.style.left = (e.clientX + 16) + 'px';
      tooltip.style.top  = (e.clientY - 16) + 'px';
      const val = getHmValue(hit);
      const sign = val >= 0 ? '+' : '';
      tooltip.innerHTML = `
        <strong>${hit.ticker}</strong> &nbsp; ${hit.name}<br>
        <span class="${val>=0?'pos':'neg'}">${hmColor === 'change' && hit.changeKnown === false ? '-' : `${sign}${val.toFixed(2)}%`}</span> &nbsp;|&nbsp;
        Mkt Cap: ${formatMarketCap(hit.marketCap)}<br>
        Price: €${formatNumber(hit.price,2)} &nbsp;|&nbsp; ${hit.country}
      `;
    } else if (tooltip) {
      tooltip.style.display = 'none';
    }
  });

  canvas.addEventListener('mouseleave', () => {
    if (tooltip) tooltip.style.display = 'none';
  });

  window.addEventListener('resize', () => {
    renderHeatmap();
  });

  document.querySelectorAll('[data-hm-group]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-hm-group]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      hmGroupBy = btn.dataset.hmGroup;
      renderHeatmap();
    });
  });

  document.querySelectorAll('[data-hm-color]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-hm-color]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      hmColor = btn.dataset.hmColor;
      renderHeatmap();
    });
  });

  renderHeatmap();
}

document.addEventListener('DOMContentLoaded', initHeatmap);
