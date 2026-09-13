"""Look up any DonutSMP player's public stats from donutstats.net (the official API is down / keyed).

The site blocks generic fetchers but answers a browser user-agent, and every player page embeds a
JSON-LD block with the numbers. Usage:  python quant/player.py NAME [NAME ...]

What the two money stats actually are, worked out from a known account: "Money Made" is LIFETIME /sell
income and "Money Spent" is LIFETIME /shop spending (dead since the June 2026 update, so it is frozen
for old accounts and zero for new ones). Neither tracks the auction house or /orders. A player holding
260M with 38K "made" and 0 "spent" got there entirely through AH and order trading, which this site
cannot see. So the useful read is: how much of a balance is explained by /sell (a farmer), and how much
is not (a trader, or a transfer recipient: /pay, off-market sales, scams, gifts).
"""
import json, re, sys, time, urllib.request, html

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def lookup(name):
    req = urllib.request.Request(f"https://www.donutstats.net/player/{name}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            doc = r.read().decode("utf-8", "ignore")
    except Exception as e:
        return {"name": name, "error": str(e)[:60]}
    out = {"name": name}
    for m in re.finditer(r'"name":"([a-z_]+)","value":"([0-9.]+)"', doc):
        out[m.group(1)] = float(m.group(2))
    t = re.sub(r"<[^>]+>", " ", doc)
    t = html.unescape(re.sub(r"\s+", " ", t))
    for lab, key in (("Money Spent", "spent"), ("Money Made", "made"), ("Playtime", "playtime_txt")):
        m = re.search(re.escape(lab) + r"\s*\$?([0-9.,]+[KMBT]?|[0-9]+d [0-9]+h)", t)
        if m:
            out[key] = m.group(1)
    return out


def money(v):
    v = float(v)
    for s, d in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= d:
            return "%.1f%s" % (v / d, s)
    return "%.0f" % v


if __name__ == "__main__":
    names = sys.argv[1:]
    print("%-18s %10s %8s %10s %10s %8s %7s %8s %9s %9s  %s" % (
        "player", "balance", "hours", "/sell life", "/shop life", "/sell/hr", "kills", "deaths", "mobs", "broken", "read"))
    for n in names:
        s = lookup(n)
        if "error" in s or "money" not in s:
            print("%-18s %s" % (n, s.get("error", "no data")))
            continue
        hrs = s.get("playtime", 0) / 3600000
        made = s.get("made", "0").replace(",", "")
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(made[-1:], 1)
        made_v = float(made.rstrip("KMBT")) * mult if made else 0
        spent = s.get("spent", "0").replace(",", "")
        mult2 = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}.get(spent[-1:], 1)
        spent_v = float(spent.rstrip("KMBT")) * mult2 if spent else 0
        bal = s["money"]
        share = made_v / bal if bal else 0
        if share >= 0.6:
            shape = "FARMER: /sell explains %d%% of balance" % (share * 100)
        elif share >= 0.15:
            shape = "MIXED: /sell is %d%% of balance, rest is AH/orders/transfers" % (share * 100)
        elif made_v > bal * 2:
            shape = "SPENT-DOWN farmer: /sold %s lifetime, holds a fraction" % money(made_v)
        else:
            shape = "AH/ORDERS or TRANSFERS: /sell is only %.1f%% of balance" % (share * 100)
        print("%-18s %10s %8.0f %10s %10s %8s %7d %8d %9d %9d  %s" % (
            n, money(bal), hrs, money(made_v), money(spent_v), money(made_v / hrs) if hrs else "-",
            s.get("kills", 0), s.get("deaths", 0), s.get("mobs_killed", 0), s.get("broken_blocks", 0), shape))
        time.sleep(0.6)
