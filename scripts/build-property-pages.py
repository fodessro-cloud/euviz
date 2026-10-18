"""Builds the property pages Google can read without running scripts:

  <out>/property-pages/<country>.html   one page per country (served as /property/<country>)
  <out>/property-pages/overvalued.html  where homes are cheap or expensive against incomes and rents

From js/housing.json (Eurostat, OECD) and js/housing-levels.json (national price per m²).
The header and footer are copied from property.html, so menu changes there carry over.

Usage: python3 scripts/build-property-pages.py <site source dir> <out dir>
"""
import html, json, re, sys
from pathlib import Path

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'build')
SITE = 'https://www.finila.com'
EU = 'EU'


def esc(v):
    return html.escape(str(v if v is not None else ''), quote=True)


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def pct(v, d=0):
    if not is_num(v):
        return '—'
    v = round(v, d) + 0.0  # no "-0 %"
    return f'{"+" if v > 0 else ""}{abs(v) if v == 0 else v:.{d}f} %'


def eur(v):
    return f'€{round(v):,}' if is_num(v) else '—'


def cls(v):
    return 'pos' if is_num(v) and v > 0 else 'neg' if is_num(v) and v < 0 else ''


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def quarter(q):
    return (q or '').replace('-', ' ')


def word(v):
    if not is_num(v):
        return ''
    return ('expensive' if v >= 15 else 'somewhat expensive' if v >= 5 else 'about average' if v > -5
            else 'somewhat cheap' if v > -15 else 'cheap')


def piece(text, name):
    """The block between <tag ...> and </tag> in property.html, so menu edits there carry over."""
    m = re.search(rf'<{name}\b.*?</{name}>', text, re.S)
    return m.group(0) if m else ''


def head(title, description, canonical):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="FINILA">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{canonical}">
  <link rel="icon" href="/css/logo.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/css/home.css">
  <link rel="stylesheet" href="/css/invest.css">
  <link rel="stylesheet" href="/css/property.css">
  <link rel="stylesheet" href="/css/header.css">
</head>
<body>

'''


def chart(series, years=10, w=760, h=260):
    """Static SVG: each series' change since the start of the period, in per cent."""
    keys = sorted(series[0][1])
    start = keys[max(0, len(keys) - 1 - years * 4)]
    lines = []
    for label, s, color, dash in series:
        ks = [k for k in sorted(s) if k >= start and k <= keys[-1]]
        if len(ks) > 1:
            lines.append((label, color, dash, [(k, (s[k] / s[ks[0]] - 1) * 100) for k in ks]))
    qs = sorted({k for *_, pts in lines for k, _ in pts})
    vals = [v for *_, pts in lines for _, v in pts] + [0]
    lo, hi = min(vals), max(vals)
    L, R, T, B = 48, 10, 10, 24
    x = lambda q: L + (w - L - R) * qs.index(q) / max(1, len(qs) - 1)
    y = lambda v: T + (h - T - B) * (1 - (v - lo) / ((hi - lo) or 1))
    step = next((s for s in (10, 20, 25, 50, 100, 200) if (hi - lo) / s <= 6), 500)
    g = []
    v = -(-lo // step) * step
    while v <= hi:
        g.append(f'<line class="{"base" if v == 0 else "g"}" x1="{L}" x2="{w - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                 f'<text class="ax" x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{"+" if v > 0 else ""}{v:g}%</text>')
        v += step
    yrs = sorted({q[:4] for q in qs})
    every = -(-len(yrs) // 8)
    for i, yr in enumerate(yrs):
        if i % every == 0:
            q = next(k for k in qs if k.startswith(yr))
            g.append(f'<text class="ax" x="{x(q):.1f}" y="{h - 6}" text-anchor="middle">{yr}</text>')
    paths = ''.join(f'<path class="ln{" dash" if dash else ""}" stroke="{color}" d="' +
                    ''.join(f'{"L" if i else "M"}{x(k):.1f},{y(v):.1f}' for i, (k, v) in enumerate(pts)) + '"/>'
                    for _, color, dash, pts in lines)
    legend = ''.join(f'<span><i class="{"dash" if dash else ""}" style="background:{color}"></i>{esc(label)}</span>'
                     for label, color, dash, _ in lines)
    return (f'<div class="i-legend">{legend}</div><div class="i-chart"><svg viewBox="0 0 {w} {h}" width="100%" '
            f'role="img" aria-label="Change in house prices since {esc(quarter(start))}">{"".join(g)}{paths}</svg></div>'), start


def tile(title, value, sub, klass=''):
    return (f'<div class="i-tile"><div class="i-tile-head">{esc(title)}</div>'
            f'<div class="i-tile-real {klass}">{value}</div><div class="i-tile-sub">{sub}</div></div>')


def country_page(code, c, lv, data, levels, header, footer, links):
    name = c['name']
    eu = data['countries'].get(EU)
    n, r = c['nominal'], c.get('real') or {}
    canonical = f'{SITE}/property/{slug(name)}'
    m2 = lv['eur'] if lv else None
    year = (c.get('latest') or '')[:4]
    title = f'Property prices in {name} {year}: price per m², growth and valuation | FINILA'
    facts = []
    if m2:
        facts.append(f'Homes in {name} cost {eur(m2)} per m² ({lv["what"]}, {lv["period"]}).')
    facts.append(f'Prices changed by {pct(n.get("1y"), 1)} in the last year and {pct(n.get("10y"))} in ten years'
                 + (f' ({pct(r.get("10y"))} after inflation).' if is_num(r.get('10y')) else '.'))
    if is_num(c.get('valuation')):
        facts.append(f'Against incomes and rents, homes are {pct(c["valuation"])} compared with their average since 2000: '
                     f'{word(c["valuation"])}.')
    description = ' '.join(facts)

    tiles = []
    if m2:
        tiles.append(tile('Price per m²', eur(m2), f'{esc(lv["what"])}, {esc(lv["period"])}'))
    tiles += [
        tile('Last 12 months', pct(n.get('1y'), 1), f'{pct(r.get("1y"), 1)} after inflation' if is_num(r.get('1y')) else 'price change', cls(n.get('1y'))),
        tile('Last 10 years', pct(n.get('10y')), f'{pct(r.get("10y"))} after inflation' if is_num(r.get('10y')) else 'price change', cls(n.get('10y'))),
        tile('Price vs. incomes', pct(c.get('vsIncome')), f'against the average since 2000: {word(c.get("vsIncome"))}' if is_num(c.get('vsIncome')) else 'not published for this country'),
        tile('Price vs. rents', pct(c.get('vsRent')), f'against the average since 2000: {word(c.get("vsRent"))}' if is_num(c.get('vsRent')) else 'not published for this country'),
    ]

    series = [('Price change', c['series']['nominal'], '#1F6FEB', False)]
    if c['series'].get('real'):
        series.append(('After inflation', c['series']['real'], '#B97A0A', False))
    if eu and code != EU:
        series.append(('European Union, price change', eu['series']['nominal'], '#8A94A6', True))
    svg, start = chart(series)

    regions = ''
    if lv and lv.get('regions'):
        rows = ''.join(f'<tr><td>{esc(x["name"])}</td><td class="r m">{eur(x["eur"])}</td></tr>' for x in lv['regions'])
        regions = f'''
  <section class="h-section">
    <div class="h-section-head"><h2>Price per m² in {esc(name)}: regions and cities</h2>
      <span class="i-sub">{esc(lv["what"])}, {esc(lv["period"])}</span></div>
    <div class="h-card i-eu"><div class="h-table-wrap"><table style="min-width:0">
      <thead><tr><th>Region or city</th><th class="r">€ per m²</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p class="h-note">Source: <a href="{esc(lv["url"])}" rel="noopener">{esc(lv["source"])}</a>.</p></div>
  </section>'''

    # Where the country stands in Europe.
    others = {k: v for k, v in data['countries'].items() if not v.get('agg')}
    rank = lambda get: sorted([k for k in others if is_num(get(k))], key=lambda k: -get(k))
    ranks = []
    for label, get, fmt in (('Price per m²', lambda k: (levels.get(k) or {}).get('eur'), eur),
                            ('10-year price change', lambda k: others[k]['nominal'].get('10y'), pct),
                            ('Cheap or expensive vs. own history', lambda k: others[k].get('valuation'), pct)):
        order = rank(get)
        if code in order:
            ranks.append(f'<tr><td>{esc(label)}</td><td class="r m">{fmt(get(code))}</td>'
                         f'<td class="r">{order.index(code) + 1} of {len(order)}</td></tr>')
    standing = f'''
  <section class="h-section">
    <div class="h-section-head"><h2>{esc(name)} compared with Europe</h2>
      <a href="/property">Map of Europe</a></div>
    <div class="h-card i-eu"><div class="h-table-wrap"><table style="min-width:0">
      <thead><tr><th>Measure</th><th class="r">{esc(name)}</th><th class="r">Rank, highest first</th></tr></thead>
      <tbody>{"".join(ranks)}</tbody></table></div>
      <p class="h-note">Price per m² compares countries' own official figures, which differ in method; see the note above each figure.
      The valuation compares each country with its own past, not with other countries. <a href="/property/overvalued">How it works</a>.</p></div>
  </section>''' if ranks and code != EU else ''

    crumbs = json.dumps({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Property prices in Europe', 'item': f'{SITE}/property'},
        {'@type': 'ListItem', 'position': 2, 'name': name, 'item': canonical}]})
    return head(title, description, canonical) + header + f'''
<main class="h-wrap i-main">
  <section class="i-intro">
    <div class="h-eyebrow"><a href="/property">PROPERTY PRICES IN EUROPE</a></div>
    <h1>Property prices in {esc(name)}</h1>
    <p>{esc(description)}</p>
  </section>

  <section class="h-section">
    <div class="h-section-head"><h2>At a glance</h2><span class="i-sub">Prices to <b>{esc(quarter(c.get("latest")))}</b></span></div>
    <div class="i-now">{"".join(tiles)}</div>
  </section>

  <section class="h-section">
    <div class="h-card i-calc">
      <div class="i-calc-head"><div><h2>House prices in {esc(name)}</h2>
        <p class="i-sub">Change since {esc(quarter(start))}, all dwellings</p></div></div>
      <div class="i-chart-wrap">{svg}</div>
      <p class="h-note">Compare with deposits, bonds, stocks and gold on <a href="/invest">Where to put money</a>.</p>
    </div>
  </section>
{regions}{standing}
  <section class="h-section">
    <div class="h-section-head"><h2>Property prices in other countries</h2></div>
    <p class="p-links">{links}</p>
  </section>
</main>
<script type="application/ld+json">{crumbs}</script>

{footer}
<script src="/js/analytics.js" defer></script>
</body>
</html>
'''


def spark(s, w=120, h=28):
    """Tiny line of a ratio against its own average (the dashed line)."""
    ks = sorted(s)
    if len(ks) < 8:
        return ''
    vals = [s[k] for k in ks]
    avg = sum(vals) / len(vals)
    lo, hi = min(vals + [avg]), max(vals + [avg])
    y = lambda v: h - 2 - (h - 4) * (v - lo) / ((hi - lo) or 1)
    pts = ' '.join(f'{w * i / (len(ks) - 1):.1f},{y(v):.1f}' for i, v in enumerate(vals))
    return (f'<svg class="p-spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<line x1="0" x2="{w}" y1="{y(avg):.1f}" y2="{y(avg):.1f}"/><polyline points="{pts}"/></svg>')


def overvalued_page(data, header, footer, links):
    rows = sorted([(k, c) for k, c in data['countries'].items() if not c.get('agg') and is_num(c.get('valuation'))],
                  key=lambda kc: -kc[1]['valuation'])
    top, bottom = rows[:3], rows[-3:][::-1]
    names = lambda xs: ', '.join(f'{c["name"]} ({pct(c["valuation"])})' for _, c in xs)
    description = (f'Where homes in Europe are expensive or cheap against incomes and rents, compared with each country\'s '
                   f'average since 2000. Most expensive: {names(top)}. Cheapest: {names(bottom)}. OECD data, updated daily.')
    body = ''.join(
        f'<tr><td><a href="/property/{slug(c["name"])}">{esc(c["name"])}</a></td>'
        f'<td class="r m">{pct(c["valuation"])}</td><td>{esc(word(c["valuation"]))}</td>'
        f'<td class="r m">{pct(c.get("vsIncome"))}</td><td>{spark(c["series"].get("income") or {})}</td>'
        f'<td class="r m">{pct(c.get("vsRent"))}</td><td>{spark(c["series"].get("rent") or {})}</td></tr>'
        for _, c in rows)
    latest = max(c.get('valuationLatest') or '' for _, c in rows)
    canonical = f'{SITE}/property/overvalued'
    title = 'Overvalued and undervalued housing markets in Europe | FINILA'
    return head(title, description, canonical) + header + f'''
<main class="h-wrap i-main">
  <section class="i-intro">
    <div class="h-eyebrow"><a href="/property">PROPERTY PRICES IN EUROPE</a></div>
    <h1>Where homes in Europe are expensive or cheap</h1>
    <p>{esc(description)}</p>
  </section>

  <section class="h-section">
    <div class="h-section-head"><h2>All countries</h2><span class="i-sub">Latest data {esc(quarter(latest))}. Dashed line: the country's average since 2000.</span></div>
    <div class="h-card i-eu p-over"><div class="h-table-wrap"><table>
      <thead><tr><th>Country</th><th class="r">Overall</th><th></th><th class="r">Price vs. incomes</th><th>Since 2000</th><th class="r">Price vs. rents</th><th>Since 2000</th></tr></thead>
      <tbody>{body}</tbody></table></div>
      <p class="h-note">Not published for Cyprus and Malta.</p></div>
  </section>

  <section class="h-section i-split">
    <div class="h-card i-method">
      <h2>How it works</h2>
      <ul>
        <li><strong>Price vs. incomes:</strong> house prices divided by household disposable income per person (OECD). It shows how many years of income a home costs, as an index.</li>
        <li><strong>Price vs. rents:</strong> house prices divided by rents (OECD). High values mean buying is dear compared with renting.</li>
        <li><strong>Against its own average:</strong> each ratio is compared with the same country's average since 2000. +20 % means homes cost a fifth more than usual for that country; it does not compare one country with another.</li>
        <li><strong>Overall:</strong> the average of the two.</li>
        <li>Expensive today does not mean prices will fall, and cheap does not mean they will rise: interest rates, population and local markets matter too. Not investment advice.</li>
      </ul>
    </div>
    <div class="h-card i-method">
      <h2>Sources</h2>
      <ul><li><a href="https://data-explorer.oecd.org/" rel="noopener">OECD analytical house price indicators</a></li>
        <li><a href="https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table" rel="noopener">Eurostat house price index</a></li></ul>
    </div>
  </section>

  <section class="h-section">
    <div class="h-section-head"><h2>Property prices by country</h2><a href="/property">Map of Europe</a></div>
    <p class="p-links">{links}</p>
  </section>
</main>

{footer}
<script src="/js/analytics.js" defer></script>
</body>
</html>
'''


def main():
    data = json.loads((SRC / 'js' / 'housing.json').read_text())
    lv_path = SRC / 'js' / 'housing-levels.json'
    levels = json.loads(lv_path.read_text())['countries'] if lv_path.exists() else {}
    page = (SRC / 'property.html').read_text()
    header = piece(page, 'header')
    header = header.replace(' aria-current="page"', '').replace('href="/property"', 'href="/property" aria-current="page"', 1)
    footer = piece(page, 'footer')
    out = OUT / 'property-pages'
    out.mkdir(parents=True, exist_ok=True)
    countries = sorted([(k, c) for k, c in data['countries'].items() if not c.get('agg')], key=lambda kc: kc[1]['name'])
    links = ' · '.join(f'<a href="/property/{slug(c["name"])}">{esc(c["name"])}</a>' for _, c in countries)
    for code, c in countries:
        (out / f'{slug(c["name"])}.html').write_text(
            country_page(code, c, levels.get(code), data, levels, header, footer, links), encoding='utf-8')
    (out / 'overvalued.html').write_text(overvalued_page(data, header, footer, links), encoding='utf-8')
    print(f'Built {len(countries)} country pages and the overvalued page in {out}')


if __name__ == '__main__':
    main()
