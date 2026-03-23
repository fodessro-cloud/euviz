// Shared utilities & navigation helpers

function setActiveNav(page) {
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.page === page);
  });
}

function changeColor(val) {
  if (val === null || val === undefined || val === '-') return '';
  return Number(val) >= 0 ? 'pos' : 'neg';
}

function sparklineHTML(ticker) {
  // Generate a fake but plausible sparkline path
  const seed = ticker.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const pts = [];
  let y = 50;
  for (let i = 0; i < 30; i++) {
    y += ((seed * (i + 1) * 1234567) % 11) - 5;
    y = Math.max(10, Math.min(90, y));
    pts.push(`${i * 10},${y}`);
  }
  const last = pts[pts.length - 1].split(',');
  const first = pts[0].split(',');
  const color = Number(last[1]) < Number(first[1]) ? '#22c55e' : '#ef4444';
  return `<svg viewBox="0 0 290 100" xmlns="http://www.w3.org/2000/svg">
    <polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="2"/>
  </svg>`;
}

function renderIndicesTicker() {
  const bar = document.getElementById('indices-bar');
  if (!bar) return;
  bar.innerHTML = INDICES.map(idx => {
    const cls = idx.change >= 0 ? 'pos' : 'neg';
    const arrow = idx.change >= 0 ? '▲' : '▼';
    return `<span class="idx-item"><span class="idx-name">${idx.name}</span>
      <span class="idx-val">${idx.value.toLocaleString('en-EU', {minimumFractionDigits:2})}</span>
      <span class="${cls}">${arrow} ${Math.abs(idx.change).toFixed(2)}%</span></span>`;
  }).join('');
}

function renderNewsBar() {
  const bar = document.getElementById('news-ticker');
  if (!bar) return;
  const items = NEWS.map(n => `<span class="news-item">${n.time} &nbsp;|&nbsp; <b>${n.source}</b>: ${n.headline}</span>`).join('&emsp;&bull;&emsp;');
  bar.innerHTML = `<div class="news-scroll">${items}&emsp;&bull;&emsp;${items}</div>`;
}

document.addEventListener('DOMContentLoaded', () => {
  renderIndicesTicker();
  renderNewsBar();
});
