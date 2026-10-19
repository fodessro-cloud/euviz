"""Interest rates in the euro: Euribor, government bond yields and term deposit rates on one chart.

Free official sources (ECB Data Portal):
  FM   ECB deposit facility rate (the ECB's key rate), Euribor 1, 3, 6 and 12 months, monthly averages since 1999
  YC   euro area government bond yields (all euro area governments, and AAA-rated only),
       2, 5 and 10 years, daily since September 2004
  MIR  rate banks paid on new household deposits fixed for up to 1 year, euro area, monthly
Deutsche Bundesbank (BBSIS): yields on corporate bonds (non-banks) of German issuers, monthly, the only
free official corporate bond yield series in euro (European indices such as iBoxx or ICE are licensed).
Writes js/rates.json: monthly series (daily yields averaged per month) and the newest value of each.
Every source is fetched on its own; one that fails keeps its values from the previous run.
"""
import csv, io, json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "js" / "rates.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FINILA data refresh; +https://www.finila.com)"}
ECB = "https://data-api.ecb.europa.eu/service/data/"
BBK = "https://api.statistiken.bundesbank.de/rest/data/"
START = "1999-01"

# key: (label, group, ECB flow/key). Groups share a colour family on the page.
SERIES = {
    "ecb": ("ECB deposit rate", "ecb", "FM/B.U2.EUR.4F.KR.DFR.LEV"),
    "eur1m": ("Euribor 1 month", "euribor", "FM/M.U2.EUR.RT.MM.EURIBOR1MD_.HSTA"),
    "eur3m": ("Euribor 3 months", "euribor", "FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA"),
    "eur6m": ("Euribor 6 months", "euribor", "FM/M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA"),
    "eur12m": ("Euribor 12 months", "euribor", "FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA"),
    "gov2y": ("Government bonds 2 years", "gov", "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y"),
    "gov5y": ("Government bonds 5 years", "gov", "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_5Y"),
    "gov10y": ("Government bonds 10 years", "gov", "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y"),
    "aaa10y": ("AAA government bonds 10 years", "aaa", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"),
    "corp": ("Corporate bonds (German firms)", "corp", "BBK:BBSIS/M.I.UMR.RD.EUR.X2000.B.A.A.R.A.A._Z._Z.A"),
    "dep1y": ("Term deposit up to 1 year", "deposit", "MIR/M.U2.B.L22.F.R.A.2250.EUR.N"),
}
SOURCES = [
    ["ECB Data Portal", "https://data.ecb.europa.eu/", "ECB deposit facility rate, Euribor (monthly averages), euro area government bond yield curve, bank deposit rates"],
    ["Deutsche Bundesbank", "https://www.bundesbank.de/en/statistics/money-and-capital-markets/interest-rates-and-yields", "yields on corporate bonds of German issuers (non-banks)"],
]


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
        return r.read().decode("utf-8")


def bundesbank(key):
    """{month: value} and the newest month from a monthly Bundesbank series (CSV: header rows, then dates)."""
    rows = list(csv.reader(io.StringIO(fetch(f"{BBK}{key}?format=csv&lang=en"))))
    months = {}
    for r in rows:
        if len(r) > 1 and len(r[0]) == 7 and r[0][4] == "-":
            try:
                months[r[0]] = round(float(r[1]), 3)
            except ValueError:
                continue
    if not months:
        raise RuntimeError("no observations")
    last = max(months)
    return {m: v for m, v in months.items() if m >= START}, {"date": last, "value": months[last]}


def ecb(key):
    """{month: value}; daily observations become monthly averages."""
    text = fetch(f"{ECB}{key}?format=csvdata&startPeriod={START}")
    acc = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            v = float(row["OBS_VALUE"])
        except (TypeError, ValueError):
            continue
        acc.setdefault(row["TIME_PERIOD"][:7], []).append((row["TIME_PERIOD"], v))
    if not acc:
        raise RuntimeError("no observations")
    months = {m: round(sum(v for _, v in obs) / len(obs), 3) for m, obs in sorted(acc.items())}
    day, value = max(o for obs in acc.values() for o in obs)   # the newest observation
    return months, {"date": day, "value": round(value, 3)}


def month_range(first, last):
    """Every month from first to last ("YYYY-MM"); a month without data stays empty (None)."""
    y, m = int(first[:4]), int(first[5:])
    while f"{y}-{m:02d}" <= last:
        yield f"{y}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    try:
        old = json.loads(OUT.read_text())
        old = {s["key"]: s for s in old.get("series", [])}
    except Exception:  # noqa: BLE001
        old = {}
    series, failed = [], []
    for key, (label, group, ecb_key) in SERIES.items():
        try:
            months, latest = bundesbank(ecb_key[4:]) if ecb_key.startswith("BBK:") else ecb(ecb_key)
            first = min(months)
            series.append({"key": key, "label": label, "group": group, "first": first,
                           "values": [months.get(m) for m in month_range(first, max(months))], "latest": latest})
            print(f"ok    {key:7} {len(months):4} months from {first}, latest {latest}")
        except Exception as e:  # noqa: BLE001 - each source fails on its own
            failed.append(key)
            print(f"FAIL  {key:7} {e}", file=sys.stderr)
            if key in old:
                series.append(old[key])
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "sources": SOURCES, "failed": failed, "series": series,
    }, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB), failed: {failed or 'none'}")
    if len(failed) > len(SERIES) // 2:
        sys.exit(1)


if __name__ == "__main__":
    main()
