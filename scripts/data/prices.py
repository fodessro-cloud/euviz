"""Daily closing prices of the screener's stocks, from Deutsche Börse's free Xetra delayed data.

Under MiFIR every trading venue must publish its trades free of charge 15 minutes later.
Deutsche Börse does this as JSON files (https://mds.deutsche-boerse.com/mds-en/real-time-data/Delayed-data);
the "daily" Xetra post-trade file holds every Xetra trade of the last trading day, in EUR.
Xetra also trades many non-German European shares (ASML, Nestlé, Novo Nordisk ...), so one
file covers most of the screener.

Writes js/prices.js (last close, change against the previous close, day range, volume per
TICKER@Country) and keeps data/prices-history.json (ISIN -> {date: close}) so the daily
change can be computed. Stocks that did not trade on Xetra keep their illustrative figures.
"""
import gzip, json, sys, tempfile, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "prices.js"
HISTORY = ROOT / "data" / "prices-history.json"
LIST_URL = "https://mfs.deutsche-boerse.com/api/DETR-posttrade"
FILE_URL = "https://mfs.deutsche-boerse.com/api/download/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}
KEEP_DAYS = 400      # enough history for 52-week ranges later

# ISIN of the share class each screener stock (js/data.js) stands for.
ISINS = {
    "SAP@Germany": "DE0007164600", "SIE@Germany": "DE0007236101", "ALV@Germany": "DE0008404005",
    "BASF@Germany": "DE000BASF111", "BMW@Germany": "DE0005190003", "MBG@Germany": "DE0007100000",
    "DTE@Germany": "DE0005557508", "DBK@Germany": "DE0005140008", "BAYN@Germany": "DE000BAY0017",
    "VOW3@Germany": "DE0007664039", "IFX@Germany": "DE0006231004", "ADS@Germany": "DE000A1EWWW0",
    "MUV2@Germany": "DE0008430026", "HEN3@Germany": "DE0006048432", "RWE@Germany": "DE0007037129",
    "CON@Germany": "DE0005439004",
    "MC@France": "FR0000121014", "TTE@France": "FR0000120271", "OR@France": "FR0000120321",
    "AIR@France": "NL0000235190", "BNP@France": "FR0000131104", "SAN@France": "FR0000120578",
    "CS@France": "FR0000120628", "RMS@France": "FR0000052292", "KER@France": "FR0000121485",
    "DG@France": "FR0000125486", "CAP@France": "FR0000125338", "RI@France": "FR0000120693",
    "ORA@France": "FR0000133308",
    "ASML@Netherlands": "NL0010273215", "SHEL@Netherlands": "GB00BP6MXD84", "INGA@Netherlands": "NL0011821202",
    "HEIA@Netherlands": "NL0000009165", "PHIA@Netherlands": "NL0000009538", "UNA@Netherlands": "GB00B10RZP78",
    "STLAM@Netherlands": "NL00150001Q9",
    "NESN@Switzerland": "CH0038863350", "ROG@Switzerland": "CH0012032048", "NOVN@Switzerland": "CH0012005267",
    "ABBN@Switzerland": "CH0012221716", "ZURN@Switzerland": "CH0011075394", "UBSG@Switzerland": "CH0244767585",
    "GIVN@Switzerland": "CH0010645932",
    "AZN@UK": "GB0009895292", "HSBA@UK": "GB0005405286", "BP@UK": "GB0007980591", "GLEN@UK": "JE00B4T3BW64",
    "RIO@UK": "GB0007188757", "GSK@UK": "GB00BN7SWP63", "ULVR@UK": "GB00B10RZP78", "DGE@UK": "GB0002374006",
    "BARC@UK": "GB0031348658", "LLOY@UK": "GB0008706128",
    "ITX@Spain": "ES0148396007", "IBE@Spain": "ES0144580Y14", "SAN@Spain": "ES0113900J37",
    "BBVA@Spain": "ES0113211835", "TEF@Spain": "ES0178430E18",
    "ENEL@Italy": "IT0003128367", "ENI@Italy": "IT0003132476", "RACE@Italy": "NL0011585146",
    "UCG@Italy": "IT0005239360", "ISP@Italy": "IT0000072618",
    "ATCO@Sweden": "SE0017486889", "VOLV@Sweden": "SE0000115446", "ERICB@Sweden": "SE0000108656",
    "HMB@Sweden": "SE0000106270", "NOVO@Denmark": "DK0062498333", "MAERSK@Denmark": "DK0010244508",
    "NOKIA@Finland": "FI0009000681", "UCB@Belgium": "BE0003739530", "ABI@Belgium": "BE0974293251",
    "CRH@Ireland": "IE0001827041", "EQNR@Norway": "NO0010096985", "OMV@Austria": "AT0000743059",
    "EDP@Portugal": "PTEDP0AM0009", "PKN@Poland": "PLPKN0000018",
}


def fetch(url, timeout=180):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def latest_daily_file():
    listing = json.loads(fetch(LIST_URL))
    daily = sorted(f for f in listing.get("CurrentFiles", []) if "-daily-" in f)
    if not daily:
        sys.exit("No daily Xetra file listed")
    name = daily[-1]
    return name, name.split("-daily-")[1][:10]


def day_summary(path, wanted):
    """Open, high, low, last price, volume and trade count per ISIN, from one day's trades."""
    days = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            t = json.loads(line)
            isin = t.get("instrumentIdentificationCode")
            if isin not in wanted or t.get("priceCurrency") != "EUR":
                continue
            if t.get("mmtModificationInd", "-") != "-":      # cancelled or amended trade reports
                continue
            p, q, ts = float(t["price"]), float(t.get("quantity") or 0), t["tradingDateAndTime"]
            d = days.get(isin)
            if not d:
                days[isin] = {"first": ts, "open": p, "last": ts, "close": p, "high": p, "low": p, "volume": q, "trades": 1}
                continue
            if ts < d["first"]:
                d["first"], d["open"] = ts, p
            if ts >= d["last"]:
                d["last"], d["close"] = ts, p
            d["high"], d["low"] = max(d["high"], p), min(d["low"], p)
            d["volume"] += q
            d["trades"] += 1
    return days


def main():
    name, day = latest_daily_file()
    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else {}
    if OUT.exists() and f"PRICES_DATE = '{day}'" in OUT.read_text():
        print(f"{day} already processed, nothing to do")
        return
    with tempfile.NamedTemporaryFile(suffix=".json.gz") as tmp:
        tmp.write(fetch(FILE_URL + name))
        tmp.flush()
        print(f"Downloaded {name}: {tmp.tell() / 1e6:.1f} MB")
        days = day_summary(tmp.name, set(ISINS.values()))

    prices, missing = {}, []
    for key, isin in ISINS.items():
        d = days.get(isin)
        if not d:
            missing.append(key)
            continue
        past = history.get(isin, {})
        prev = max((k for k in past if k < day), default=None)
        prev_close = past[prev] if prev else None
        prices[key] = {
            "isin": isin, "price": round(d["close"], 4), "open": round(d["open"], 4),
            "high": round(d["high"], 4), "low": round(d["low"], 4),
            "volume": int(d["volume"]), "trades": d["trades"],
            "prevClose": prev_close,
            "change": round((d["close"] / prev_close - 1) * 100, 2) if prev_close else None,
        }
        past[day] = round(d["close"], 4)
        history[isin] = dict(sorted(past.items())[-KEEP_DAYS:])

    HISTORY.parent.mkdir(exist_ok=True)
    HISTORY.write_text(json.dumps(history, separators=(",", ":"), sort_keys=True))
    OUT.write_text(
        "// Generated by scripts/data/prices.py from Deutsche Börse's free Xetra delayed data. Do not edit by hand.\n"
        f"const PRICES_DATE = '{day}';\n"
        f"const PRICES_UPDATED = '{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC';\n"
        f"const PRICES = {json.dumps(prices, separators=(',', ':'), ensure_ascii=False)};\n"
    )
    print(f"Xetra {day}: prices for {len(prices)} of {len(ISINS)} stocks")
    for k in missing:
        print(f"  not traded on Xetra: {k} ({ISINS[k]})")
    for k, p in prices.items():
        print(f"  {k:20} {p['isin']} close {p['price']:>10} trades {p['trades']:>6} change {p['change']}")


if __name__ == "__main__":
    main()
