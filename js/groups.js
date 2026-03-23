// Groups page logic

let groupBy = 'sector';
let groupSort = 'marketCap';
let groupSortDir = -1;

function aggregateGroups() {
  const map = {};
  for (const s of STOCKS) {
    const key = s[groupBy] || 'Other';
    if (!map[key]) map[key] = { name: key, stocks: [], marketCap: 0, changeSum: 0, count: 0 };
    map[key].stocks.push(s);
    map[key].marketCap += s.marketCap;
    map[key].changeSum += s.change;
    map[key].count++;
  }

  return Object.values(map).map(g => ({
    name: g.name,
    count: g.count,
    marketCap: g.marketCap,
    avgChange: g.changeSum / g.count,
    avgPE: avg(g.stocks.map(s => s.pe).filter(Boolean)),
    avgDividend: avg(g.stocks.map(s => s.dividend)),
    avgROE: avg(g.stocks.map(s => s.roe)),
    avgBeta: avg(g.stocks.map(s => s.beta)),
    avgRevGrowth: avg(g.stocks.map(s => s.revenueGrowth)),
    avgMargin: avg(g.stocks.map(s => s.netMargin)),
    topStock: g.stocks.sort((a,b) => b.marketCap - a.marketCap)[0],
    performersUp: g.stocks.filter(s => s.change > 0).length,
    performersDown: g.stocks.filter(s => s.change < 0).length,
  }));
}

function avg(arr) {
  const valid = arr.filter(v => v !== null && v !== undefined);
  if (!valid.length) return null;
  return valid.reduce((a, b) => a + b, 0) / valid.length;
}

function renderGroups() {
  const groups = aggregateGroups().sort((a, b) => {
    let va = a[groupSort], vb = b[groupSort];
    if (typeof va === 'string') return va.localeCompare(vb) * groupSortDir;
    if (va === null) va = groupSortDir > 0 ? Infinity : -Infinity;
    if (vb === null) vb = groupSortDir > 0 ? Infinity : -Infinity;
    return (va - vb) * groupSortDir;
  });

  const tbody = document.getElementById('groups-tbody');
  if (!tbody) return;

  tbody.innerHTML = groups.map((g, i) => `
    <tr class="group-row" onclick="toggleGroupDetail('${g.name.replace(/'/g,"\\'")}')">
      <td>${i + 1}</td>
      <td><strong>${g.name}</strong></td>
      <td>${g.count}</td>
      <td>${formatMarketCap(g.marketCap)}</td>
      <td><span class="${changeColor(g.avgChange)}">${formatPct(g.avgChange)}</span></td>
      <td>${g.avgPE ? formatNumber(g.avgPE,1) : '-'}</td>
      <td>${formatNumber(g.avgDividend,2)}%</td>
      <td><span class="${changeColor(g.avgROE)}">${g.avgROE ? formatNumber(g.avgROE,1)+'%' : '-'}</span></td>
      <td><span class="${changeColor(g.avgRevGrowth)}">${formatPct(g.avgRevGrowth)}</span></td>
      <td><span class="${changeColor(g.avgMargin)}">${g.avgMargin ? formatNumber(g.avgMargin,1)+'%' : '-'}</span></td>
      <td>${formatNumber(g.avgBeta,2)}</td>
      <td>
        <div class="perf-bar">
          <div class="perf-up" style="width:${Math.round(g.performersUp/g.count*100)}%"></div>
          <div class="perf-down" style="width:${Math.round(g.performersDown/g.count*100)}%"></div>
        </div>
        <span class="perf-label">${g.performersUp}↑ ${g.performersDown}↓</span>
      </td>
    </tr>
    <tr class="group-detail" id="detail-${g.name.replace(/\s/g,'-')}" style="display:none">
      <td colspan="12">
        <div class="group-stocks-grid">
          ${g.topStock ? renderGroupStocks(g.name) : ''}
        </div>
      </td>
    </tr>
  `).join('');
}

function renderGroupStocks(groupName) {
  const stocks = STOCKS.filter(s => s[groupBy] === groupName)
    .sort((a, b) => b.marketCap - a.marketCap);
  return stocks.map(s => `
    <div class="mini-card" onclick="openGroupStock('${s.ticker}')">
      <div class="mini-ticker">${s.ticker}</div>
      <div class="mini-name">${s.name}</div>
      <div class="mini-price">€${formatNumber(s.price,2)}</div>
      <div class="mini-change ${changeColor(s.change)}">${formatPct(s.change)}</div>
      <div class="mini-cap">${formatMarketCap(s.marketCap)}</div>
    </div>
  `).join('');
}

function toggleGroupDetail(name) {
  const id = 'detail-' + name.replace(/\s/g,'-');
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
}

function openGroupStock(ticker) {
  // redirect to screener with modal
  window.open(`index.html?stock=${ticker}`, '_blank');
}

function onGroupSortClick(key) {
  if (groupSort === key) groupSortDir *= -1;
  else { groupSort = key; groupSortDir = -1; }
  renderGroups();
}

document.addEventListener('DOMContentLoaded', () => {
  renderGroups();

  document.querySelectorAll('[data-group-by]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-group-by]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      groupBy = btn.dataset.groupBy;
      renderGroups();
    });
  });
});
