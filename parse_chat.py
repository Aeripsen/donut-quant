import re, csv, glob, os, sys, json
from collections import defaultdict
SP = os.path.dirname(os.path.abspath(__file__))
logdir = os.path.join(SP, "logs")

def money(s):
    s = s.replace(",", "").replace(" ", "").upper()
    m = re.match(r"\$?([0-9.]+)([KMB]?)", s)
    if not m: return None
    v = float(m.group(1)); u = m.group(2)
    return v * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[u]

# gather chat lines with date from filename
rows = []
files = sorted(glob.glob(os.path.join(logdir, "*.log")))
for f in files:
    base = os.path.basename(f)
    m = re.match(r"(?:p1_)?(\d{4}-\d{2}-\d{2})", base)
    date = m.group(1) if m else ("2026-08-29" if "latest" in base else "?")
    prof = "p1" if base.startswith("p1_") or "profile1" in base else "main"
    with open(f, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "[CHAT]" not in line: continue
            mm = re.match(r"\[(\d\d:\d\d:\d\d)\] \[[^\]]+\]: (?:\[System\] )?\[CHAT\] (.*)", line.rstrip("\n"))
            if not mm: continue
            t, msg = mm.group(1), mm.group(2)
            rows.append((prof, date, t, msg))

pat_listed = re.compile(r"^(You|\w+) listed (\d+) (.+?) for \$ ?([0-9.,]+[KMB]?)$")
pat_bought = re.compile(r"^(You|\w+) bought (\d+) (.+?) for \$ ?([0-9.,]+[KMB]?)$")
pat_boughtyour = re.compile(r"^(\w+) bought your (.+?) for \$ ?([0-9.,]+[KMB]?)( while you were away)?$")
pat_soldmulti = re.compile(r"^(You|\w+) sold multiple items for \$ ?([0-9.,]+[KMB]?)$")
pat_earned = re.compile(r"^You earned \$ ?([0-9.,]+[KMB]?) from auction while you were away$")
pat_bal = re.compile(r"^\$ ?([0-9.,]+[KMB]?)$")
events = []
other_money = []
for prof, date, t, msg in rows:
    e = None
    m = pat_listed.match(msg)
    if m:
        e = dict(type="listed", actor=m.group(1), qty=int(m.group(2)), item=m.group(3), price=money(m.group(4)))
    if not e:
        m = pat_bought.match(msg)
        if m: e = dict(type="bought", actor=m.group(1), qty=int(m.group(2)), item=m.group(3), price=money(m.group(4)))
    if not e:
        m = pat_boughtyour.match(msg)
        if m: e = dict(type="sold_to", actor=m.group(1), qty=None, item=m.group(2), price=money(m.group(3)))
    if not e:
        m = pat_soldmulti.match(msg)
        if m: e = dict(type="sold_multi", actor=m.group(1), qty=None, item="(multiple)", price=money(m.group(2)))
    if not e:
        m = pat_earned.match(msg)
        if m: e = dict(type="earned_away", actor="You", qty=None, item="(auction)", price=money(m.group(1)))
    if not e:
        m = pat_bal.match(msg)
        if m: e = dict(type="balance", actor="You", qty=None, item="(balance)", price=money(m.group(1)))
    if e:
        e.update(profile=prof, date=date, time=t, raw=msg)
        e["unit"] = (e["price"]/e["qty"]) if e.get("qty") else None
        events.append(e)
    elif "$" in msg:
        other_money.append((date, t, msg))

with open(os.path.join(SP, "ah_events.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["profile","date","time","type","actor","qty","item","price","unit","raw"])
    w.writeheader()
    for e in events: w.writerow(e)
print("events:", len(events))
from collections import Counter
print(Counter(e["type"] for e in events))
print("actors:", Counter(e["actor"] for e in events).most_common(10))
print("unparsed $ lines:", len(other_money))
for x in other_money[:40]: print("  ", x)
# per-item summary of unit prices (listed vs bought)
summ = defaultdict(lambda: defaultdict(list))
for e in events:
    if e["unit"] is not None:
        summ[e["item"]][e["type"]].append(e["unit"])
def med(xs):
    xs = sorted(xs); n=len(xs)
    return xs[n//2] if n%2 else (xs[n//2-1]+xs[n//2])/2
out=[]
for item, d in summ.items():
    out.append((item, {k:(len(v), min(v), med(v), max(v)) for k,v in d.items()}))
out.sort(key=lambda x: -sum(len(v) for v in summ[x[0]].values()))
print("\nPER-ITEM UNIT PRICES (n, min, median, max):")
for item, d in out:
    print(f"{item:32s}", {k:(n, round(a), round(b), round(c)) for k,(n,a,b,c) in d.items()})
