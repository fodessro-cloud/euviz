"""Managers' transactions (MAR art. 19) published by Finansinspektionen, Sweden.

Downloads the last 60 days from FI's insider register export and writes
js/insiders.json for the site. FI publishes the register as public information.
"""
import csv, io, json, sys, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DAYS = 60
URL = ("https://marknadssok.fi.se/Publiceringsklient/en-GB/Search/Search?SearchFunctionType=Insyn"
       "&Publiceringsdatum.From={frm}&Publiceringsdatum.To={to}&button=export")
UA = {"User-Agent": "FINILA data refresh (finila.com)"}

# English export headers -> our field names
COLUMNS = {
    "Publication date": "published", "Issuer": "issuer", "LEI-code": "lei",
    "Person discharging managerial responsibilities": "person", "Position": "position",
    "Closely associated": "associated", "Nature of transaction": "nature", "Instrument name": "instrument",
    "Instrument type": "instrumentType", "Intrument type": "instrumentType",
    "Amendment": "amendment", "Initial notification": "initial",
    "Linked to share option programme": "optionProgramme", "ISIN": "isin", "Transaction date": "date", "Volume": "volume",
    "Unit": "unit", "Price": "price", "Currency": "currency", "Status": "status", "Trading venue": "venue",
}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def decode(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[1:200:2].count(0) > 50:   # FI sends UTF-16LE without a byte order mark
        return raw.decode("utf-16-le")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def to_date(s):
    s = (s or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return s or None


def to_num(s):
    s = (s or "").strip().replace("\xa0", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def ecb_rates():
    try:
        root = ET.fromstring(fetch("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"))
        rates = {c.get("currency"): float(c.get("rate")) for c in root.iter() if c.get("currency")}
        rates["EUR"] = 1.0
        return rates
    except Exception as e:
        print(f"  ! ECB rates: {e}")
        return {"EUR": 1.0}


def download(frm, to):
    """Rows published between frm and to; FI caps an export at 1000 rows, so long windows are split."""
    text = decode(fetch(URL.format(frm=frm.isoformat(), to=to.isoformat())))
    first = text.splitlines()[0] if text else ""
    delim = ";" if first.count(";") >= first.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text, newline=""), delimiter=delim))
    if len(rows) >= 1000 and to > frm:
        mid = frm + (to - frm) // 2
        return download(frm, mid) + download(mid + timedelta(days=1), to)
    print(f"  {frm}..{to}: {len(rows)} rows")
    return rows


def main():
    today = date.today()
    rows = download(today - timedelta(days=DAYS), today)
    unknown = [h for h in (rows[0].keys() if rows else []) if h and h.strip() not in COLUMNS]
    if unknown:
        print(f"  unmapped columns: {unknown}")
    fx = ecb_rates()
    out = []
    for r in rows:
        t = {COLUMNS[k.strip()]: (v or "").strip() for k, v in r.items() if k and k.strip() in COLUMNS}
        if not t.get("issuer"):
            continue
        t["published"], t["date"] = to_date(t.get("published")), to_date(t.get("date"))
        t["volume"], t["price"] = to_num(t.get("volume")), to_num(t.get("price"))
        rate = fx.get(t.get("currency") or "")
        if t.get("unit") == "Amount":
            value = t["volume"]
        else:
            value = t["volume"] * t["price"] if t["volume"] is not None and t["price"] is not None else None
        t["valueEur"] = round(value / rate) if value is not None and rate else None
        # Counts toward "insiders buying/selling": the current version of a share purchase or sale
        # on a trading venue. Off-venue deals (transfers between own holding companies, takeover
        # bids, subscriptions) and revised or cancelled reports would inflate the totals.
        t["signal"] = (t.get("status") == "Current" and t.get("instrumentType") == "Share"
                       and t.get("nature") in ("Acquisition", "Disposal") and bool(t.get("isin"))
                       and t.get("venue") != "Outside a trading venue")
        out.append(t)
    if not out:
        print("no transactions parsed")
        return 1
    out.sort(key=lambda t: (t.get("published") or "", t.get("valueEur") or 0), reverse=True)
    (ROOT / "js/insiders.json").write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "source": "Finansinspektionen (Sweden)",
         "days": DAYS, "rows": out}, ensure_ascii=False, separators=(",", ":")))
    # Small summary for the homepage card, so it does not download the whole register.
    buys = {}
    for t in out:
        if t["signal"] and t.get("nature") == "Acquisition" and (t.get("valueEur") or 0) > 0:
            b = buys.setdefault(t["issuer"], {"issuer": t["issuer"], "v": 0, "people": set()})
            b["v"] += t["valueEur"]
            b["people"].add(t.get("person"))
    top = sorted(buys.values(), key=lambda b: -b["v"])[:8]
    (ROOT / "js/insiders-home.json").write_text(json.dumps(
        {"buys": [{"issuer": b["issuer"], "v": b["v"], "people": len(b["people"])} for b in top]},
        ensure_ascii=False, separators=(",", ":")))
    natures = {}
    for t in out:
        natures[t.get("nature")] = natures.get(t.get("nature"), 0) + 1
    print(f"{len(out)} transactions; natures: {sorted(natures.items(), key=lambda x: -x[1])[:12]}")
    for t in out[:5]:
        print(json.dumps(t, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
