"""Where to put money: real returns of savings and investments in every European country.

Free official sources, monthly:
  ECB Data Portal  bank deposit rates (MIR), 10-year government bond yields (IRS), HICP index up to
                   2025, ECB deposit facility rate, EURO STOXX 50 index, euro exchange rates
  Eurostat         HICP annual inflation (COICOP 2018 series, from 2026), house price index (quarterly)
  World Bank       gold price (Pink Sheet, monthly averages)
Writes js/invest.json: per country a "wealth index" per asset (what 1 unit of local currency became),
which the page turns into "10,000 put away N years ago", plus the latest rates.
Every source is fetched on its own; one that fails keeps its values from the previous run
(data/invest-raw.json).
"""
import csv, io, json, re, sys, urllib.error, urllib.request, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "invest.json"
RAW = ROOT / "data" / "invest-raw.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}
START = "1999-01"

# code: (name, currency, euro member). U2 = euro area as a whole.
COUNTRIES = {
    "U2": ("Euro area", "EUR", True),
    "AT": ("Austria", "EUR", True), "BE": ("Belgium", "EUR", True), "BG": ("Bulgaria", "EUR", True),
    "HR": ("Croatia", "EUR", True), "CY": ("Cyprus", "EUR", True), "EE": ("Estonia", "EUR", True),
    "FI": ("Finland", "EUR", True), "FR": ("France", "EUR", True), "DE": ("Germany", "EUR", True),
    "GR": ("Greece", "EUR", True), "IE": ("Ireland", "EUR", True), "IT": ("Italy", "EUR", True),
    "LV": ("Latvia", "EUR", True), "LT": ("Lithuania", "EUR", True), "LU": ("Luxembourg", "EUR", True),
    "MT": ("Malta", "EUR", True), "NL": ("Netherlands", "EUR", True), "PT": ("Portugal", "EUR", True),
    "SK": ("Slovakia", "EUR", True), "SI": ("Slovenia", "EUR", True), "ES": ("Spain", "EUR", True),
    "CZ": ("Czechia", "CZK", False), "DK": ("Denmark", "DKK", False), "HU": ("Hungary", "HUF", False),
    "PL": ("Poland", "PLN", False), "RO": ("Romania", "RON", False), "SE": ("Sweden", "SEK", False),
    "NO": ("Norway", "NOK", False), "CH": ("Switzerland", "CHF", False), "GB": ("United Kingdom", "GBP", False),
    "IS": ("Iceland", "ISK", False),
}
ESTAT_GEO = {"U2": "EA20", "GR": "EL", "GB": "UK"}
CURRENCIES = sorted({c[1] for c in COUNTRIES.values()} - {"EUR"})

ECB = "https://data-api.ecb.europa.eu/service/data/"
ESTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
WB_PAGE = "https://www.worldbank.org/en/research/commodity-markets"

SOURCES = [
    ["ECB Data Portal", "https://data.ecb.europa.eu/", "bank deposit rates, 10-year government bond yields, inflation index to 2025, ECB rate, EURO STOXX 50, exchange rates"],
    ["Eurostat", "https://ec.europa.eu/eurostat/web/hicp", "inflation (HICP) and house price index"],
    ["World Bank Pink Sheet", WB_PAGE, "gold price (monthly average)"],
]


def fetch(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
        b = r.read()
    return b if binary else b.decode("utf-8-sig")


def month_avg(points):
    acc = {}
    for p, v in points:
        acc.setdefault(p[:7], []).append(v)
    return {m: sum(v) / len(v) for m, v in sorted(acc.items())}


def ecb_multi(flow, key, area_pos=1, cur_pos=None, want_cur=None):
    """One ECB request for many countries: {area: {month: value}}; for MIR/IRS keeps the series in the
    country's own currency (EUR for euro countries)."""
    text = fetch(f"{ECB}{flow}/{key}?format=csvdata&startPeriod={START}")
    series = {}
    for row in csv.DictReader(io.StringIO(text)):
        parts = row["KEY"].split(".")[1:]
        try:
            v = float(row["OBS_VALUE"])
        except (TypeError, ValueError):
            continue
        area = parts[area_pos]
        if cur_pos is not None and want_cur and parts[cur_pos] != want_cur(area):
            continue
        series.setdefault(area, []).append((row["TIME_PERIOD"], v))
    return {a: month_avg(p) for a, p in series.items()}


def estat_multi(dataset, query):
    """Eurostat JSON-stat for many geos; quarters become their middle month. {geo: {month: value}}
    If Eurostat refuses the whole list (one unknown geo), asks for each geo on its own."""
    try:
        return estat_parse(fetch(f"{ESTAT}{dataset}?{query}"))
    except urllib.error.HTTPError:
        geos = re.findall(r"geo=([A-Z0-9]+)", query)
        rest = re.sub(r"geo=[A-Z0-9]+&?", "", query)
        out = {}
        for g in geos:
            try:
                out.update(estat_parse(fetch(f"{ESTAT}{dataset}?geo={g}&{rest}")))
            except Exception as e:  # noqa: BLE001
                print(f"      {dataset} {g}: {e}", file=sys.stderr)
        return out


def estat_parse(text):
    d = json.loads(text)
    ids, sizes = d["id"], d["size"]
    cat = {k: d["dimension"][k]["category"]["index"] for k in ids}
    for k in ids:
        if k not in ("geo", "time") and len(cat[k]) != 1:
            raise RuntimeError(f"dimension {k} has {len(cat[k])} values")
    strides, s = {}, 1
    for k, n in zip(reversed(ids), reversed(sizes)):
        strides[k] = s
        s *= n
    out = {}
    for g, gi in cat["geo"].items():
        pts = {}
        for t, ti in cat["time"].items():
            v = d["value"].get(str(gi * strides["geo"] + ti * strides["time"]))
            if v is None:
                continue
            if "-Q" in t:
                y, q = t.split("-Q")
                t = f"{y}-{int(q) * 3 - 1:02d}"
            pts[t] = float(v)
        if pts:
            out[g] = dict(sorted(pts.items()))
    return out


def xlsx_sheet(raw, name):
    """Rows of one sheet of an .xlsx file (standard library only)."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = None
    for sh in wb.find("m:sheets", ns):
        if sh.get("name").strip().lower() == name.lower():
            rid = sh.get(f"{{{ns['r']}}}id")
            for rel in rels:
                if rel.get("Id") == rid:
                    target = "xl/" + rel.get("Target").lstrip("/").removeprefix("xl/")
    if not target:
        raise RuntimeError(f"sheet {name} not found")
    rows = []
    for row in ET.fromstring(z.read(target)).iter(f"{{{ns['m']}}}row"):
        cells = {}
        for c in row.findall("m:c", ns):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v = c.find("m:v", ns)
            if v is None:
                t = c.find("m:is/m:t", ns)
                cells[col] = t.text if t is not None else None
            elif c.get("t") == "s":
                cells[col] = shared[int(v.text)]
            else:
                cells[col] = v.text
        rows.append(cells)
    return rows


def gold_usd():
    page = fetch(WB_PAGE)
    links = re.findall(r'href="([^"]*CMO-Historical-Data-Monthly\.xlsx)"', page)
    if not links:
        raise RuntimeError("Pink Sheet link not found on the World Bank page")
    url = links[0] if links[0].startswith("http") else "https://www.worldbank.org" + links[0]
    rows = xlsx_sheet(fetch(url, binary=True), "Monthly Prices")
    col = None
    for r in rows[:10]:
        for k, v in r.items():
            if isinstance(v, str) and v.strip().lower() == "gold":
                col = k
    if not col:
        raise RuntimeError("gold column not found in the Pink Sheet")
    out = {}
    for r in rows:
        m = re.fullmatch(r"(\d{4})M(\d{2})", str(r.get("A") or "").strip())
        if m and r.get(col):
            try:
                out[f"{m.group(1)}-{m.group(2)}"] = float(r[col])
            except ValueError:
                pass
    return {k: v for k, v in out.items() if k >= START}


def fill_months(s):
    """Linear interpolation between known months (quarterly house prices -> monthly)."""
    keys = sorted(s)
    out = {}
    for a, b in zip(keys, keys[1:]):
        ia, ib = midx(a), midx(b)
        for i in range(ia, ib):
            out[mstr(i)] = s[a] + (s[b] - s[a]) * (i - ia) / (ib - ia)
    if keys:
        out[keys[-1]] = s[keys[-1]]
    return out


def midx(m):
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def mstr(i):
    return f"{i // 12}-{i % 12 + 1:02d}"


def chain_prices(index, annual):
    """HICP index up to 2025 (ECB) extended month by month with the new annual rates (Eurostat)."""
    idx = dict(index)
    if not idx:
        return idx
    for m in sorted(annual):
        prev = mstr(midx(m) - 12)
        if m > max(idx) and prev in idx:
            idx[m] = idx[prev] * (1 + annual[m] / 100)
    return idx


def wealth_from_rate(rates):
    w, out = 1.0, {}
    for m in sorted(rates):
        out[m] = w
        w *= 1 + rates[m] / 100 / 12
    return out


def wealth_from_bond_yield(yields, years=10):
    """Constant-maturity 10-year government bond fund: interest plus the price change from the yield
    move (modified duration of a par bond). A standard approximation of a bond index."""
    ms = sorted(yields)
    out, w = ({ms[0]: 1.0} if ms else {}), 1.0
    for a, b in zip(ms, ms[1:]):
        if midx(b) - midx(a) != 1:
            break
        y0, y1 = yields[a] / 100, yields[b] / 100
        dur = (1 - (1 + y0) ** -years) / y0 if abs(y0) > 1e-6 else years
        w *= 1 + y0 / 12 - dur * (y1 - y0)
        out[b] = w
    return out


def contiguous_tail(s):
    """The latest unbroken run of months (series with a gap would compound wrongly)."""
    ms = sorted(s)
    start = 0
    for j in range(1, len(ms)):
        if midx(ms[j]) - midx(ms[j - 1]) != 1:
            start = j
    return {m: s[m] for m in ms[start:]}


def pack(s, digits=4):
    """{month: v} -> [first month, [v...]] normalised to 1 at the first month."""
    s = contiguous_tail({m: v for m, v in s.items() if m >= START})
    if not s:
        return None
    ms = sorted(s)
    base = s[ms[0]]
    return [ms[0], [round(s[m] / base, digits) for m in ms]]


def main():
    try:
        old = json.loads(RAW.read_text()) if RAW.exists() else {}
    except Exception:  # noqa: BLE001
        old = {}
    raw, failed = {}, []
    areas = "+".join(COUNTRIES)
    local = lambda a: COUNTRIES.get(a, ("", "EUR"))[1]  # noqa: E731
    geos = "&".join(f"geo={ESTAT_GEO.get(c, c)}" for c in COUNTRIES)
    back = {ESTAT_GEO.get(c, c): c for c in COUNTRIES}
    jobs = {
        "hicp": lambda: ecb_multi("ICP", f"M.{areas}.N.000000.4.INX"),
        "hicp_es": lambda: {back[g]: v for g, v in estat_multi("prc_hicp_midx", f"{geos}&coicop=CP00&unit=I15").items()},
        "infl_old": lambda: ecb_multi("ICP", f"M.{areas}.N.000000.4.ANR"),
        "infl": lambda: {back[g]: v for g, v in estat_multi("prc_hicp_minr", f"{geos}&coicop18=TOTAL&unit=RCH_A&sinceTimePeriod=2024-01").items()},
        "dep1y": lambda: ecb_multi("MIR", f"M.{areas}.B.L22.F.R.A.2250..N", cur_pos=8, want_cur=local),
        "depon": lambda: ecb_multi("MIR", f"M.{areas}.B.L21.A.R.A.2250..N", cur_pos=8, want_cur=local),
        "bond10": lambda: ecb_multi("IRS", f"M.{areas}.L.L40.CI.0000..N.Z", cur_pos=6, want_cur=local),
        "house": lambda: {back[g]: fill_months(v) for g, v in estat_multi("prc_hpi_q", f"{geos}&purchase=TOTAL&unit=I15_Q").items()},
        "fx": lambda: ecb_multi("EXR", f"M.{'+'.join(CURRENCIES + ['USD'])}.EUR.SP00.A", area_pos=1),
        "dfr": lambda: ecb_multi("FM", "B.U2.EUR.4F.KR.DFR.LEV"),
        "stoxx50": lambda: ecb_multi("FM", "M.U2.EUR.DS.EI.DJES50I.HSTA"),
        "gold_usd": lambda: {"W": gold_usd()},
    }
    for name, job in jobs.items():
        try:
            raw[name] = job()
            n = sum(len(v) for v in raw[name].values())
            print(f"ok    {name:9} {len(raw[name]):3} series, {n:6} months, newest {max(max(v) for v in raw[name].values() if v)}")
        except Exception as e:  # noqa: BLE001 - each source fails on its own
            failed.append(name)
            print(f"FAIL  {name:9} {e}", file=sys.stderr)
            if name in old:
                raw[name] = old[name]
    RAW.write_text(json.dumps(raw, separators=(",", ":")))

    fx = raw.get("fx", {})
    usd = fx.get("USD") or {}
    stoxx = raw.get("stoxx50", {}).get("U2", {})
    gold = {m: v / usd[m] for m, v in raw.get("gold_usd", {}).get("W", {}).items() if m in usd} if usd else {}
    if not usd:
        try:  # gold needs EUR/USD, fetched only when gold is
            usd = ecb_multi("EXR", "M.USD.EUR.SP00.A").get("USD", {})
            gold = {m: v / usd[m] for m, v in raw.get("gold_usd", {}).get("W", {}).items() if m in usd}
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  eurusd    {e}", file=sys.stderr)

    def in_cur(s, c):
        if c == "EUR":
            return s
        r = fx.get(c, {})
        return {m: v * r[m] for m, v in s.items() if m in r}

    assets, now, countries = {}, {"c": {}}, {}
    for c in ["EUR"] + CURRENCIES:
        a = {"stocks": pack(in_cur(stoxx, c)), "gold": pack(in_cur(gold, c))}
        assets[c] = {k: v for k, v in a.items() if v}

    def last(s):
        if not s:
            return None
        m = max(s)
        return {"month": m, "value": round(s[m], 3)}

    def yoy(s):
        if not s:
            return None
        m = max(s)
        p = mstr(midx(m) - 12)
        return {"month": m, "value": round((s[m] / s[p] - 1) * 100, 2)} if p in s else None

    for code, (name, cur, euro) in COUNTRIES.items():
        g = lambda k: raw.get(k, {}).get(code) or {}  # noqa: E731
        infl = {**g("infl_old"), **g("infl")}
        prices = chain_prices(g("hicp") or g("hicp_es"), infl)
        a = {
            "deposit": pack(wealth_from_rate(contiguous_tail(g("dep1y")))) if g("dep1y") else None,
            "savings": pack(wealth_from_rate(contiguous_tail(g("depon")))) if g("depon") else None,
            "bonds": pack(wealth_from_bond_yield(contiguous_tail(g("bond10")))) if g("bond10") else None,
            "house": pack(g("house")) if g("house") else None,
            "prices": pack(prices) if prices else None,
        }
        a = {k: v for k, v in a.items() if v}
        if not infl or max(infl) < mstr(midx(max(max(v) for v in raw.get("infl", {}).values() if v)) - 24):
            print(f"skip  {code}: no recent inflation data")   # e.g. the UK, out of EU statistics since 2020
            continue
        countries[code] = {"name": name, "cur": cur, "euro": euro}
        assets[code] = a
        now["c"][code] = {
            "inflation": last(infl), "deposit1y": last(g("dep1y")), "savings": last(g("depon")),
            "bond10": last(g("bond10")), "house_12m": yoy(g("house")),
            "stocks_12m": yoy(in_cur(stoxx, cur)), "gold_12m": yoy(in_cur(gold, cur)),
        }
    now["dfr"] = last(raw.get("dfr", {}).get("U2"))

    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "sources": SOURCES, "failed": failed, "countries": countries, "now": now, "assets": assets,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB), {len(countries)} countries, failed: {failed or 'none'}")
    for code in countries:
        n = now["c"][code]
        print(f"  {code} infl {n['inflation']} dep {n['deposit1y']} bond {n['bond10']} house {n['house_12m']} assets {sorted(assets[code])}")
    if len(failed) > len(jobs) // 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
