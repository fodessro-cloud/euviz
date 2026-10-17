"""Temporary: which concepts carry share counts, gross profit and borrowings in a few reports."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from fundamentals import BASE, get, extract, metrics
from universe import list_filings  # noqa: E402

LEIS = ["21380068P1DRHMJ8KU70", "549300TTCXZOGZM2EY83", "549300HGV012CNC8JD22", "724500C9GNBV20UYRX36"]
PAT = re.compile(r"^(CurrentAssets|CurrentLiabilities|Assets|CashFlowsFromUsedInOperatingActivities|ProfitLoss|NoncurrentBorrowings|LongtermBorrowings|NoncurrentFinancialLiabilities|NoncurrentLeaseLiabilities)$")
issuers = list_filings()
for lei in LEIS:
    rec = issuers.get(lei)
    if not rec:
        print(lei, "not found"); continue
    f = rec["filings"][0]
    print("==", rec["name"], f["period_end"], f["json_url"])
    xj = get(BASE + f["json_url"].replace(" ", "%20"))
    cur, prev, ccy, end, _ = extract(xj, f["period_end"])
    print("  CUR", {k: v for k, v in cur.items()})
    print("  PREV", {k: v for k, v in prev.items()})
    m = metrics(cur, prev)
    print("  F", m.get("fscore"), m.get("fscoreTests"))
    seen = {}
    for fact in (xj or {}).get("facts", {}).values():
        d = fact.get("dimensions", {})
        c = d.get("concept", "")
        if PAT.search(c.split(":")[-1]) and not re.search(r"Explanatory|Description|Policy|Text", c):
            extra = sorted(set(d) - {"concept", "entity", "period", "unit", "language"})
            key = (c, tuple(extra))
            if key not in seen:
                seen[key] = (d.get("period"), d.get("unit"), fact.get("value"))
    for (c, extra), v in sorted(seen.items())[:80]:
        print(" ", c, list(extra), v)
