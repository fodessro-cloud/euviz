"""Where to put money: real returns of savings and investments in Slovakia and the euro area.

Free official sources, all monthly:
  ECB Data Portal   HICP inflation, bank deposit rates (MIR), 10-year government bond yields (IRS),
                    ECB deposit facility rate, EURO STOXX 50 index, EUR/USD
  Eurostat          house price index (quarterly, interpolated to months)
  Bundesbank        gold price (London fixing)
Writes js/invest.json: monthly series plus a "wealth index" per asset (what 1 euro became),
which the page turns into "EUR 10,000 invested N years ago". Every series is fetched on its own;
one that fails keeps its values from the previous run.
"""
import csv, io, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "invest.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}
START = "1999-01"
REGIONS = {"SK": "Slovakia", "U2": "Euro area"}
EUROSTAT_GEO = {"SK": "SK", "U2": "EA20"}

ECB = "https://data-api.ecb.europa.eu/service/data/{}?format=csvdata&startPeriod=" + START
BBK = "https://api.statistiken.bundesbank.de/rest/data/{}?startPeriod=" + START
ESTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{}"

# Each series: list of candidate URLs (first that works wins), monthly values "YYYY-MM" -> float.
def ecb(key):
    return ECB.format(key.replace(".", "/", 1))

SERIES = {
    "dfr": [ecb("FM.B.U2.EUR.4F.KR.DFR.LEV"), ecb("FM.D.U2.EUR.4F.KR.DFR.LEV")],
    "stoxx50": [ecb("FM.M.U2.EUR.DS.EI.DJES50I.HSTA")],
    "eurusd": [ecb("EXR.M.USD.EUR.SP00.A")],
    "gold_eur": [BBK.format("BBEX3/M.XAU.EUR.EA.AC.C06"), BBK.format("BBEX3/D.XAU.EUR.EA.AC.C04")],
    "gold_usd": [BBK.format("BBEX3/M.XAU.USD.EA.AC.C06"), BBK.format("BBEX3/D.XAU.USD.EA.AC.C05")],
}
for r in REGIONS:
    SERIES[f"hicp_{r}"] = [ecb(f"ICP.M.{r}.N.000000.4.INX")]
    SERIES[f"infl_{r}"] = [ecb(f"ICP.M.{r}.N.000000.4.ANR")]
    SERIES[f"dep1y_{r}"] = [ecb(f"MIR.M.{r}.B.L22.F.R.A.2250.EUR.N")]      # households, agreed maturity up to 1 year, new business
    SERIES[f"depon_{r}"] = [ecb(f"MIR.M.{r}.B.L21.A.R.A.2250.EUR.N")]      # households, overnight (current/savings account)
    SERIES[f"bond10_{r}"] = [ecb(f"IRS.M.{r}.L.L40.CI.0000.EUR.N.Z")]      # 10-year government bond yield
    SERIES[f"house_{r}"] = [ESTAT.format(f"prc_hpi_q?geo={EUROSTAT_GEO[r]}&purchase=TOTAL&unit=I15_Q")]

SOURCES = [
    ["ECB Data Portal", "https://data.ecb.europa.eu/", "inflation (HICP), bank deposit rates, government bond yields, ECB rate, EURO STOXX 50, EUR/USD"],
    ["Eurostat", "https://ec.europa.eu/eurostat/databrowser/view/prc_hpi_q/default/table", "house price index"],
    ["Deutsche Bundesbank", "https://www.bundesbank.de/en/statistics/time-series-databases", "gold price (London fixing)"],
]


def fetch(url, accept=None):
    h = dict(UA)
    if accept:
        h["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
        return r.read().decode("utf-8-sig")


def month_avg(points):
    """[(period, value)] with daily/business/monthly periods -> {"YYYY-MM": monthly mean}."""
    acc = {}
    for p, v in points:
        acc.setdefault(p[:7], []).append(v)
    return {m: sum(v) / len(v) for m, v in sorted(acc.items())}


def parse_csv(text):
    rows = csv.DictReader(io.StringIO(text))
    out = []
    for row in rows:
        p = row.get("TIME_PERIOD") or row.get("TIME_PERIOD ") or ""
        v = row.get("OBS_VALUE")
        try:
            out.append((p.strip(), float(v)))
        except (TypeError, ValueError):
            pass
    return out


def parse_jsonstat(text):
    """Eurostat JSON-stat with one value per time period; quarters become their middle month."""
    d = json.loads(text)
    times = d["dimension"]["time"]["category"]["index"]
    stride = 1
    ids, sizes = d["id"], d["size"]
    for dim, size in zip(reversed(ids), reversed(sizes)):
        if dim == "time":
            break
        stride *= size
    out = []
    for t, i in times.items():
        v = d["value"].get(str(i * stride))
        if v is None:
            continue
        if "-Q" in t:
            y, q = t.split("-Q")
            t = f"{y}-{int(q) * 3 - 1:02d}"
        out.append((t, float(v)))
    return out


def get(name, urls):
    errors = []
    for url in urls:
        try:
            if "bundesbank" in url:
                pts = parse_csv(fetch(url, "application/vnd.sdmx.data+csv;version=1.0.0"))
            elif "eurostat" in url:
                pts = parse_jsonstat(fetch(url))
            else:
                pts = parse_csv(fetch(url))
            if pts:
                return month_avg(pts)
            errors.append(f"{url}: no data")
        except Exception as e:  # noqa: BLE001 - each source fails on its own
            errors.append(f"{url}: {e}")
    raise RuntimeError("; ".join(errors))


def fill_months(s):
    """Linear interpolation between known months (quarterly house prices -> monthly)."""
    if not s:
        return s
    keys = sorted(s)
    def idx(m):
        return int(m[:4]) * 12 + int(m[5:7]) - 1
    out = {}
    for a, b in zip(keys, keys[1:]):
        ia, ib = idx(a), idx(b)
        for i in range(ia, ib):
            out[f"{i // 12}-{i % 12 + 1:02d}"] = s[a] + (s[b] - s[a]) * (i - ia) / (ib - ia)
    out[keys[-1]] = s[keys[-1]]
    return out


def wealth_from_rate(rates):
    """Money kept on a deposit, rate (% p.a.) of each month earned for that month."""
    w, out = 1.0, {}
    for m in sorted(rates):
        out[m] = w
        w *= 1 + rates[m] / 100 / 12
    return out


def wealth_from_bond_yield(yields, years=10):
    """Constant-maturity 10-year government bond fund: coupon carry plus price change from the
    yield move (modified duration of a par bond). A standard approximation of a bond index."""
    ms = sorted(yields)
    w, out = 1.0, {ms[0]: 1.0} if ms else {}
    for a, b in zip(ms, ms[1:]):
        y0, y1 = yields[a] / 100, yields[b] / 100
        dur = (1 - (1 + y0) ** -years) / y0 if abs(y0) > 1e-6 else years
        w *= 1 + y0 / 12 - dur * (y1 - y0)
        out[b] = w
    return out


def normalise(s):
    ms = sorted(s)
    return {m: s[m] / s[ms[0]] for m in ms} if ms else {}


def rnd(s, n=5):
    return [[m, round(v, n)] for m, v in sorted(s.items()) if m >= START]


def main():
    old = {}
    if OUT.exists():
        try:
            old = {k: dict(v) for k, v in json.loads(OUT.read_text())["raw"].items()}
        except Exception:  # noqa: BLE001
            old = {}
    raw, failed = {}, []
    for name, urls in SERIES.items():
        try:
            raw[name] = get(name, urls)
            print(f"ok    {name:12} {len(raw[name]):4} months, last {max(raw[name])} = {raw[name][max(raw[name])]:.3f}")
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            print(f"FAIL  {name:12} {e}", file=sys.stderr)
            if name in old:
                raw[name] = old[name]
    if "gold_eur" not in raw and "gold_usd" in raw and "eurusd" in raw:
        raw["gold_eur"] = {m: v / raw["eurusd"][m] for m, v in raw["gold_usd"].items() if m in raw["eurusd"]}
        print("gold_eur computed from gold_usd / eurusd")

    assets = {}
    for r in REGIONS:
        a = {}
        if f"dep1y_{r}" in raw:
            a["deposit"] = wealth_from_rate(raw[f"dep1y_{r}"])
        if f"depon_{r}" in raw:
            a["savings"] = wealth_from_rate(raw[f"depon_{r}"])
        if f"bond10_{r}" in raw:
            a["bonds"] = wealth_from_bond_yield(raw[f"bond10_{r}"])
        if "stoxx50" in raw:
            a["stocks"] = normalise(raw["stoxx50"])
        if "gold_eur" in raw:
            a["gold"] = normalise(raw["gold_eur"])
        if f"house_{r}" in raw:
            a["house"] = normalise(fill_months(raw[f"house_{r}"]))
        if f"hicp_{r}" in raw:
            a["prices"] = normalise(raw[f"hicp_{r}"])
        assets[r] = {k: rnd(v) for k, v in a.items()}

    def last(name):
        s = raw.get(name)
        if not s:
            return None
        m = max(s)
        return {"month": m, "value": round(s[m], 3)}

    def yoy(name):
        s = raw.get(name)
        if not s:
            return None
        m = max(s)
        y, mo = int(m[:4]), m[5:7]
        prev = f"{y - 1}-{mo}"
        if prev not in s:
            return None
        return {"month": m, "value": round((s[m] / s[prev] - 1) * 100, 2)}

    now = {"dfr": last("dfr"), "stocks_12m": yoy("stoxx50"), "gold_12m": yoy("gold_eur") if "gold_eur" in raw else None}
    for r in REGIONS:
        now[r] = {
            "inflation": last(f"infl_{r}"), "deposit1y": last(f"dep1y_{r}"), "savings": last(f"depon_{r}"),
            "bond10": last(f"bond10_{r}"), "house_12m": yoy(f"house_{r}"),
        }

    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "regions": REGIONS, "sources": SOURCES, "failed": failed,
        "now": now, "assets": assets,
        "raw": {k: rnd(v, 4) for k, v in raw.items()},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB), failed: {failed or 'none'}")
    if len(failed) > len(SERIES) // 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
