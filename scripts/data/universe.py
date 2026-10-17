"""Build FINILA's company universe: every issuer on filings.xbrl.org with an annual
report for fiscal 2024 or later, with the figures from its newest report.

Names, tickers and industries come from Wikidata (CC0), FX rates from the ECB.
Reports already read are cached in data/cache/universe.json, so a daily run only
downloads new reports. Writes js/companies.json (served to the site) and
data/universe-report.txt.
"""
import json, os, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent))
from fundamentals import BASE, ROOT, get, extract, metrics, UA   # noqa: E402

import urllib.request

MIN_PERIOD = "2024-01-01"
CACHE = ROOT / "data/cache/universe.json"
CACHE_VERSION = 3          # bump when metrics() changes, so every report is read again
WIKIDATA_CACHE = ROOT / "data/cache/wikidata.json"
# Shares with a European ISIN only: drops e.g. Toyota or Royal Bank of Canada, which file in London too.
EUROPE = set("AT BE BG CH CY CZ DE DK EE ES FI FR GB GG GR HR HU IE IM IS IT JE LI LT LU LV MT NL NO PL PT RO SE SI SK FO GI".split())
BUDGET = float(os.environ.get("FINILA_BUDGET_MIN", "300")) * 60   # stop downloading after this
WORKERS = 6
START = time.time()

# Wikidata industry words -> FINILA sector. First match wins.
SECTORS = [
    ("Financials", ["bank", "insurance", "financial", "asset management", "investment", "reinsurance", "stock exchange", "payment"]),
    ("Real Estate", ["real estate", "property", "reit"]),
    ("Healthcare", ["pharma", "biotech", "medical", "health", "hospital", "drug", "diagnostic"]),
    ("Technology", ["software", "semiconductor", "information technology", "computer", "electronics", "internet", "it service", "video game"]),
    ("Communication", ["telecom", "media", "broadcast", "publishing", "advertising", "entertainment"]),
    ("Energy", ["oil and gas", "oil industry", "natural gas", "gas industry", "petroleum", "energy", "coal", "renewable"]),
    ("Utilities", ["utility", "electric", "water supply", "power"]),
    ("Materials", ["chemical", "mining", "metal", "steel", "paper", "cement", "building material", "packaging", "gold"]),
    ("Consumer Staples", ["food", "dairy", "consumer goods", "beverage", "brew", "tobacco", "retail", "supermarket", "household", "cosmetic", "agricultur"]),
    ("Consumer Discretionary", ["automotive", "car", "luxury", "fashion", "clothing", "apparel", "hotel", "restaurant", "travel", "leisure", "gambling", "furniture", "e-commerce"]),
    ("Industrials", ["engineering", "construction", "aerospace", "defence", "defense", "transport", "logistics", "shipping", "airline", "machine", "industrial", "manufactur", "rail", "conglomerate"]),
]
WIKIDATA_QUERY = """
SELECT ?lei ?item ?itemLabel ?ticker ?exLabel ?indLabel WHERE {
  ?item wdt:P1278 ?lei; p:P414 ?st.
  ?st ps:P414 ?ex.
  OPTIONAL { ?st pq:P249 ?ticker }
  OPTIONAL { ?item wdt:P452 ?ind }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def log(msg):
    print(msg, flush=True)


def list_filings():
    """Newest-first candidate reports per LEI, with the issuer name and country."""
    by_lei, url, pages = {}, f"{BASE}/api/filings?include=entity&page[size]=500&sort=-period_end", 0
    while url:
        data = get(url)
        if not data:
            break
        names = {e["id"]: e["attributes"] for e in data.get("included", []) if e["type"] == "entity"}
        oldest = None
        for f in data.get("data", []):
            a = f["attributes"]
            pe = a.get("period_end") or ""
            oldest = pe
            if not a.get("json_url") or not (MIN_PERIOD <= pe <= f"{date.today().year + 1}-12-31"):
                continue
            ent = names.get(f["relationships"]["entity"]["data"]["id"], {})
            lei = ent.get("identifier")
            if not lei:
                continue
            rec = by_lei.setdefault(lei, {"name": ent.get("name"), "country": a.get("country"), "filings": []})
            rec["filings"].append(a)
        pages += 1
        if oldest and oldest < MIN_PERIOD and oldest[:4] > "1900":
            break   # sorted by period end, everything after this is older
        nxt = data.get("links", {}).get("next")
        url = (nxt if nxt.startswith("http") else BASE + nxt) if nxt else None
    for rec in by_lei.values():
        rec["filings"].sort(key=lambda a: (a["period_end"], a["processed"]), reverse=True)
    log(f"{len(by_lei)} issuers with a report for {MIN_PERIOD[:4]} or later ({pages} pages)")
    return by_lei


def read_report(lei, rec):
    for f in rec["filings"][:3]:
        xj = get(BASE + f["json_url"])
        if not xj:
            continue
        cur, prev, currency, fy_end, _ = extract(xj, f["period_end"])
        if "revenue" in cur or "net" in cur:
            row = metrics(cur, prev)
            row.update({"currency": currency, "periodEnd": fy_end.isoformat(),
                        "source": BASE + f["viewer_url"] if f.get("viewer_url") else None})
            return f["fxo_id"], row
    return rec["filings"][0]["fxo_id"], None


def wikidata():
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(WIKIDATA_QUERY)
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/sparql-results+json"})
    for attempt in range(3):   # the query service rate-limits to about one query a minute when busy
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                rows = json.load(r)["results"]["bindings"]
            break
        except Exception as e:
            err = e
            time.sleep(75)
    else:
        log(f"  ! Wikidata: {err}; using the last saved copy")
        try:
            return {k: {**v, "tickers": [tuple(t) for t in v["tickers"]], "industries": set(v["industries"])}
                    for k, v in json.loads(WIKIDATA_CACHE.read_text()).items()}
        except Exception:
            return {}
    out = {}
    for b in rows:
        lei = b["lei"]["value"]
        w = out.setdefault(lei, {"name": b["itemLabel"]["value"], "tickers": [], "industries": set()})
        if "ticker" in b:
            w["tickers"].append((b["ticker"]["value"], b.get("exLabel", {}).get("value", "")))
        if "indLabel" in b:
            w["industries"].add(b["indLabel"]["value"])
    log(f"{len(out)} listed companies with an LEI on Wikidata")
    WIKIDATA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    WIKIDATA_CACHE.write_text(json.dumps({k: {**v, "industries": sorted(v["industries"])} for k, v in out.items()},
                                         ensure_ascii=False, separators=(",", ":")))
    return out


def ecb_rates():
    try:
        with urllib.request.urlopen("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=60) as r:
            root = ET.fromstring(r.read())
        rates = {c.get("currency"): float(c.get("rate")) for c in root.iter() if c.get("currency")}
        rates["EUR"] = 1.0
        return rates
    except Exception as e:
        log(f"  ! ECB rates: {e}")
        return {"EUR": 1.0}


def sector_of(industries):
    """The sector most of the company's Wikidata industries point to (Unilever: food, dairy and
    consumer goods, not the one industry that mentions oils)."""
    votes = {}
    for ind in industries:
        for rank, (sector, words) in enumerate(SECTORS):
            if any(re.search(r"\b" + re.escape(w), ind.lower()) for w in words):
                votes[sector] = (votes.get(sector, (0, rank))[0] + 1, rank)
                break
    return max(votes, key=lambda k: (votes[k][0], -votes[k][1])) if votes else None


# Main exchange of each country, to pick the home ticker among Wikidata's listings.
HOME_EXCHANGE = {
    "FR": "Paris", "NL": "Amsterdam", "BE": "Brussels", "PT": "Lisbon", "IE": "Dublin|Irish", "GB": "London",
    "SE": "Stockholm", "DK": "Copenhagen", "FI": "Helsinki", "NO": "Oslo", "IS": "Iceland", "IT": "Milan|Italiana",
    "ES": "Madrid|Spanish|Bolsa", "AT": "Vienna|Wiener", "PL": "Warsaw", "GR": "Athens", "LU": "Luxembourg",
    "DE": "Frankfurt|Xetra", "CZ": "Prague", "HU": "Budapest", "SK": "Bratislava", "SI": "Ljubljana",
    "HR": "Zagreb", "RO": "Bucharest", "BG": "Sofia", "EE": "Tallinn", "LV": "Riga", "LT": "Vilnius",
    "CY": "Cyprus", "MT": "Malta",
}
FOREIGN = re.compile(r"New York|NASDAQ(?! (Stockholm|Copenhagen|Helsinki|Iceland|Riga|Tallinn|Vilnius))|OTC|Over-the-counter|Pink|Tokyo|Toronto", re.I)


def pick_ticker(tickers, country):
    home = HOME_EXCHANGE.get(country)
    for t, ex in tickers:
        if home and re.search(home, ex, re.I):
            return t, ex
    for t, ex in tickers:
        if not FOREIGN.search(ex):
            return t, ex
    return None, None


def tidy(name):
    name = re.sub(r"\s+", " ", name or "").strip()
    return name.title() if name.isupper() and len(name) > 4 else name


FIELDS = ["lei", "isin", "name", "country", "ticker", "exchange", "mic", "sector", "industry", "currency", "periodEnd",
          "revenueEur", "revenue", "ebitda", "operatingProfit", "netIncome", "operatingCashFlow", "capex", "fcf",
          "dividendsPaid", "equity", "assets", "cash", "debt", "netDebt", "eps", "roe", "ebitdaMargin",
          "operatingMargin", "netMargin", "fcfMargin", "netDebtToEbitda", "revenueGrowth", "netIncomeGrowth",
          "fscore", "fscoreTests", "payoutFcf", "payoutNet", "financial", "source"]


def main():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    issuers = list_filings()
    listed_file = ROOT / "data/listed.json"
    listed = json.loads(listed_file.read_text()) if listed_file.exists() else {}
    todo = [(lei, rec) for lei, rec in issuers.items()
            if (cache.get(lei, {}).get("fxo") != rec["filings"][0]["fxo_id"] or cache[lei].get("v") != CACHE_VERSION)
            and (not listed or lei in listed)]
    log(f"{len(todo)} reports to read, {len(issuers) - len(todo)} cached")
    done = 0
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {}
        for lei, rec in todo:
            futures[pool.submit(lambda l=lei, r=rec: read_report(l, r) if time.time() - START < BUDGET else None)] = lei
        for fut in as_completed(futures):
            res = fut.result()
            if res is None:
                continue
            cache[futures[fut]] = {"fxo": res[0], "row": res[1], "v": CACHE_VERSION}
            done += 1
            if done % 200 == 0:
                log(f"  read {done} reports")
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(cache, separators=(",", ":")))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, separators=(",", ":")))
    log(f"read {done} reports this run")

    wd, fx = wikidata(), ecb_rates()
    log(f"{len(listed)} issuers with listed shares (FIRDS); {sum(1 for l in issuers if l in listed)} of them file reports here")
    rows, no_figures = [], 0
    for lei, rec in issuers.items():
        row = cache.get(lei, {}).get("row")
        if not row:
            no_figures += 1
            continue
        w = wd.get(lei, {})
        ticker, exchange = pick_ticker(w.get("tickers", []), rec["country"])
        listing = listed.get(lei)
        if listed and not listing:
            continue   # no shares on a European venue: bond-only issuers, unlisted companies
        if listing and listing["isin"][:2] not in EUROPE:
            continue
        rate = fx.get(row.get("currency") or "")
        rev_eur = round(row["revenue"] / rate, 1) if row.get("revenue") is not None and rate else None
        name = w.get("name") if w.get("name") and not re.fullmatch(r"Q\d+", w["name"]) else tidy(rec["name"])
        # The ISIN shows the company's home country; the filing country can be where it filed (Boliden in Norway).
        country = listing["isin"][:2] if listing and listing["isin"][:2] in EUROPE - {"GG", "JE", "IM", "GI", "FO"} else rec["country"]
        rows.append({**row, "lei": lei, "name": name, "country": country,
                     "isin": listing["isin"] if listing else None,
                     "mic": (listing or {}).get("mics", [None])[0] if listing and listing.get("mics") else None,
                     "ticker": ticker, "exchange": exchange, "sector": sector_of(w.get("industries", [])),
                     "industry": ", ".join(sorted(w.get("industries", [])))[:60] or None, "revenueEur": rev_eur})
    rows.sort(key=lambda r: -(r["revenueEur"] or 0))
    out = {"updated": date.today().isoformat(), "fields": FIELDS,
           "rows": [[r.get(k) for k in FIELDS] for r in rows]}
    (ROOT / "js/companies.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))

    by_country = {}
    for r in rows:
        by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    report = [f"{len(rows)} companies with figures, {no_figures} without usable figures",
              f"with ticker: {sum(1 for r in rows if r['ticker'])}, with sector: {sum(1 for r in rows if r['sector'])}",
              f"with F-score: {sum(1 for r in rows if r.get('fscore') is not None)}, "
              f"F-score 8-9: {sum(1 for r in rows if (r.get('fscore') or 0) >= 8)}, "
              f"with dividend cover: {sum(1 for r in rows if r.get('payoutFcf') is not None)}",
              "by country: " + ", ".join(f"{k} {v}" for k, v in sorted(by_country.items(), key=lambda x: -x[1])),
              "", "largest 40 by revenue:"]
    report += [f"{r['name'][:34]:34} {r['country']} {r['ticker'] or '-':8} {r['sector'] or '-':22} "
               f"{r['periodEnd']} rev€={r['revenueEur']} ebitda={r['ebitda']} fcf={r['fcf']} roe={r['roe']} F={r.get('fscore')} {r.get('fscoreTests')}"
               for r in rows[:40]]
    (ROOT / "data/universe-report.txt").write_text("\n".join(report) + "\n")
    log("\n".join(report))


if __name__ == "__main__":
    sys.exit(main())
