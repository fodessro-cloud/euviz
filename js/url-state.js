// Keeps a page's choices (country, period, filters, search) in its address, so a copied link opens the same view.
// Values are readable words (?country=slovenia&pe=under-15), not list positions, so links keep working when data changes.
const urlSlug = s => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const urlParam = k => new URLSearchParams(location.search).get(k);

// Sets or removes (null, '' or undefined) the given parameters without reloading or adding a history step.
function urlSet(obj) {
  const u = new URL(location.href);
  Object.entries(obj).forEach(([k, v]) => { if (v === null || v === undefined || v === '') u.searchParams.delete(k); else u.searchParams.set(k, v); });
  if (u.href !== location.href) history.replaceState(null, '', u);
}

// Filter dropdowns of the screener, shorts and insiders: FILTERS = [{ id, options|opts: [[label, test]], def }],
// filters = { id: option index }. "any" in the address clears a filter that has a default.
function urlReadFilters(FILTERS, filters, optsOf) {
  FILTERS.forEach(f => {
    const v = urlParam(f.id), sel = document.getElementById('f-' + f.id);
    if (v === null) return;
    if (v === 'any') { delete filters[f.id]; if (sel) sel.value = ''; return; }
    const i = optsOf(f).findIndex(([label]) => urlSlug(label) === v);
    if (i >= 0) { filters[f.id] = i; if (sel) sel.value = String(i); }
  });
}
function urlWriteFilters(FILTERS, filters, optsOf, extra = {}) {
  const o = { ...extra };
  FILTERS.forEach(f => {
    const i = filters[f.id];
    o[f.id] = i === undefined ? (f.def !== undefined ? 'any' : null) : i === f.def ? null : urlSlug(optsOf(f)[i][0]);
  });
  urlSet(o);
}
