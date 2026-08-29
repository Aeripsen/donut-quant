"""Pull the official DonutSMP API into a local SQLite db and print a quick market read.

Setup (one time):
  1. In game type  /api   and copy the key it gives you (never paste it in chat or Discord).
  2. Put it in a file next to this script called  donut_api_key.txt  (one line, just the key).
     /api revoke  kills the key if it ever leaks.

Run:
  python fetch_official.py listings "ghast tear"     -> live AH listings for a search, cheapest first
  python fetch_official.py transactions 30           -> pull 30 pages of settled sales into donut.sqlite
  python fetch_official.py stats the player           -> your /stats
  python fetch_official.py report                    -> per-item median sale price + volume from the db

Limits: 250 requests/minute per key. Transactions have no enchant or potion detail (server limitation).
"""
import json, os, sqlite3, sys, time, statistics, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://api.donutsmp.net"
KEY_FILE = os.path.join(HERE, "donut_api_key.txt")
DB = os.path.join(HERE, "donut.sqlite")


def key():
    if not os.path.exists(KEY_FILE):
        sys.exit("missing donut_api_key.txt (type /api in game and save the key there)")
    return open(KEY_FILE, encoding="utf-8").read().strip()


def call(path, body=None):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body else None, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def db():
    con = sqlite3.connect(DB)
    con.execute("""create table if not exists tx (sold_ms integer, item_id text, display_name text, count integer, price real,
                   unit real, seller text, enchants text, lore text, primary key (sold_ms, item_id, seller, price))""")
    con.execute("""create table if not exists listing (seen_ms integer, item_id text, display_name text, count integer, price real,
                   unit real, seller text, time_left integer, enchants text)""")
    return con


def listings(search, pages=3, sort="lowest_price"):
    rows = []
    for p in range(1, pages + 1):
        d = call(f"/v1/auction/list/{p}", {"search": search, "sort": sort})
        res = d.get("result") or []
        if not res:
            break
        for a in res:
            it = a.get("item") or {}
            c = it.get("count") or 1
            rows.append((int(time.time() * 1000), it.get("id"), it.get("display_name"), c, a.get("price"), (a.get("price") or 0) / c,
                         (a.get("seller") or {}).get("name"), a.get("time_left"), json.dumps((it.get("enchants") or {}).get("enchantments"))))
    con = db(); con.executemany("insert into listing values (?,?,?,?,?,?,?,?,?)", rows); con.commit()
    for r in sorted(rows, key=lambda x: x[5])[:40]:
        print(f"{r[2]:32s} x{r[3]:<3} {r[4]:>14,.0f}  unit {r[5]:>12,.1f}  {r[6]}  ench={r[8]}")
    print(len(rows), "listings saved")


def transactions(pages=20):
    con = db(); n = 0
    for p in range(1, pages + 1):
        d = call(f"/v1/auction/transactions/{p}")
        res = d.get("result") or []
        if not res:
            break
        for a in res:
            it = a.get("item") or {}
            c = it.get("count") or 1
            try:
                con.execute("insert or ignore into tx values (?,?,?,?,?,?,?,?,?)",
                            (a.get("unixMillisDateSold"), it.get("id"), it.get("display_name"), c, a.get("price"), (a.get("price") or 0) / c,
                             (a.get("seller") or {}).get("name"), json.dumps((it.get("enchants") or {}).get("enchantments")), json.dumps(it.get("lore"))))
                n += 1
            except sqlite3.Error:
                pass
        con.commit(); time.sleep(0.3)   # 250/min limit
    print(n, "transactions inserted")


def report(min_n=5):
    con = db()
    cur = con.execute("select item_id, display_name, unit, count from tx where unit > 0")
    agg = {}
    for item_id, name, unit, count in cur:
        a = agg.setdefault(item_id, {"name": name, "units": [], "vol": 0})
        a["units"].append(unit); a["vol"] += count
    rows = [(k, v["name"], len(v["units"]), statistics.median(v["units"]), min(v["units"]), v["vol"]) for k, v in agg.items() if len(v["units"]) >= min_n]
    rows.sort(key=lambda r: -r[5])
    print(f"{'item':36s} {'n':>5} {'median unit':>14} {'min unit':>12} {'units sold':>11}")
    for r in rows[:150]:
        print(f"{r[1][:36]:36s} {r[2]:>5} {r[3]:>14,.1f} {r[4]:>12,.1f} {r[5]:>11,}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "listings":
        listings(" ".join(sys.argv[2:]) or "")
    elif cmd == "transactions":
        transactions(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "stats":
        print(json.dumps(call(f"/v1/stats/{sys.argv[2]}"), indent=1))
    else:
        report()
